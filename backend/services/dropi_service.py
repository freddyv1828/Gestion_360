import requests
from datetime import datetime
from config import DROPI_API_BASE_URL, DROPI_API_KEY
from database import get_company_db, get_marketplace_db

VIRTUAL_WAREHOUSE_CODE = "WH-DROPI"
VIRTUAL_WAREHOUSE_NAME = "Almacén Virtual Dropi"

# Catálogo de prueba usado únicamente cuando no hay credenciales reales de Dropi
# configuradas en el entorno, para permitir el desarrollo de la vitrina móvil.
_MOCK_CATALOG = [
    {"dropi_sku": "DRP-00123", "name": "Audífonos Bluetooth TWS Pro", "price": 18.99, "stock": 250},
    {"dropi_sku": "DRP-00456", "name": "Smartwatch Deportivo X7", "price": 34.50, "stock": 120},
    {"dropi_sku": "DRP-00789", "name": "Cargador Inalámbrico Rápido 15W", "price": 12.25, "stock": 300},
]


class DropiService:

    @staticmethod
    def ensure_virtual_warehouse(company_db_name):
        """Garantiza que exista el Almacén Virtual Dropi en la empresa (idempotente)."""
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos de la empresa no disponible."

        wh_col = db['warehouses']
        if wh_col.find_one({"code": VIRTUAL_WAREHOUSE_CODE}):
            return True, "El Almacén Virtual Dropi ya existe."

        wh_col.insert_one({
            "name": VIRTUAL_WAREHOUSE_NAME,
            "code": VIRTUAL_WAREHOUSE_CODE,
            "type": "dropshipping",
            "is_active": True,
            "created_at": datetime.utcnow()
        })
        return True, "Almacén Virtual Dropi creado con éxito."

    @staticmethod
    def _fetch_remote_catalog():
        """Consulta la API oficial de Dropi. Retorna None si no hay credenciales configuradas."""
        if not DROPI_API_KEY:
            return None
        try:
            response = requests.get(
                f"{DROPI_API_BASE_URL}/api/products",
                headers={"Authorization": f"Bearer {DROPI_API_KEY}"},
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            print(f"Error consultando la API de Dropi: {e}")
            return None

    @staticmethod
    def sync_catalog_to_marketplace():
        """
        Sincroniza el catálogo de Dropi hacia gestion360_marketplace.dropi_catalog.
        Usa la API real si DROPI_API_KEY está configurada; de lo contrario, siembra
        un catálogo de prueba para habilitar el desarrollo de la vitrina móvil.
        """
        marketplace_db = get_marketplace_db()
        catalog_col = marketplace_db['dropi_catalog']

        remote_items = DropiService._fetch_remote_catalog()
        using_mock = remote_items is None
        items = remote_items if remote_items is not None else _MOCK_CATALOG

        synced = 0
        for item in items:
            catalog_col.update_one(
                {"dropi_sku": item["dropi_sku"]},
                {"$set": {
                    "name": item["name"],
                    "price": item["price"],
                    "stock": item.get("stock", 0),
                    "source": "mock" if using_mock else "dropi_api",
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
            synced += 1

        suffix = " (datos de prueba — configure DROPI_API_KEY para producción)" if using_mock else ""
        return True, f"Catálogo Dropi sincronizado: {synced} productos{suffix}."
