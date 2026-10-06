"""
Importa un catálogo de prueba como productos reales de la empresa indicada, generando
3 variantes por artículo (para tener suficiente volumen con el que probar paginación y
facturación). Conserva la imagen real de cada producto.

Fuente primaria: FakeStore API (https://fakestoreapi.com). Si no responde (es una API
pública sin SLA y puede caerse), se usa automáticamente DummyJSON como respaldo —
misma idea (catálogo de prueba con imágenes reales), más variedad de artículos.

Uso:
    python scripts/seed_fakestore_catalog.py gestion360_j401234567
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import requests
from database import get_company_db
from services.commercial_service import CommercialService

FAKESTORE_URL = "https://fakestoreapi.com/products"
DUMMYJSON_URL = "https://dummyjson.com/products?limit=30"
MAX_BASE_PRODUCTS = 30
VARIANT_SUFFIXES = ["Estándar", "Pro", "Edición Especial"]


def _fetch_base_products():
    """Intenta FakeStore primero; si falla, cae a DummyJSON. Normaliza ambos a
    una forma común: {id, title, category, price, image}."""
    try:
        response = requests.get(FAKESTORE_URL, timeout=15)
        if response.ok:
            raw = response.json()[:MAX_BASE_PRODUCTS]
            print(f"Fuente: FakeStore API ({len(raw)} productos).")
            return [
                {"id": p["id"], "title": p["title"], "category": p.get("category", "General"),
                 "price": p.get("price", 10), "image": p.get("image")}
                for p in raw
            ]
        print(f"FakeStore API respondió {response.status_code} — usando respaldo DummyJSON.")
    except requests.RequestException as e:
        print(f"FakeStore API no disponible ({e}) — usando respaldo DummyJSON.")

    response = requests.get(DUMMYJSON_URL, timeout=15)
    response.raise_for_status()
    raw = response.json().get("products", [])[:MAX_BASE_PRODUCTS]
    print(f"Fuente: DummyJSON ({len(raw)} productos).")
    return [
        {"id": p["id"], "title": p["title"], "category": p.get("category", "General"),
         "price": p.get("price", 10), "image": p.get("thumbnail") or (p.get("images") or [None])[0]}
        for p in raw
    ]


def run(company_db_name, creator_email="seed@gestion360.com", rif="J-40123456-7"):
    db = get_company_db(company_db_name)

    warehouses = CommercialService.get_warehouses(company_db_name)
    if not warehouses:
        ok, msg = CommercialService.create_warehouse(
            company_db_name, {"name": "Almacén Principal", "code": "WH-001", "type": "sales"}
        )
        print(f"[warehouse] {msg}")
        warehouses = CommercialService.get_warehouses(company_db_name)
    warehouse_id = warehouses[0]['_id']

    base_products = _fetch_base_products()

    created = 0
    for p in base_products:
        base_name = p['title'][:80]
        category = (p.get('category') or 'General').title()
        base_price = float(p.get('price', 10))
        image_url = p.get('image')

        for i, suffix in enumerate(VARIANT_SUFFIXES):
            sku = f"DEMO-{p['id']:03d}-{i + 1}"
            variant_name = f"{base_name} ({suffix})"
            price = round(base_price * (1 + i * 0.15), 2)
            cost = round(price * 0.6, 2)
            stock = random.randint(15, 80)

            form_data = {
                "name": variant_name,
                "sku": sku,
                "category": category,
                "brand": "FakeStore Demo",
                "warehouse_id": warehouse_id,
                "cost": str(cost),
                "price": str(price),
                "iva_rate": "16",
                "stock": str(stock),
                "min_stock": "5",
                "unit_type": "unidad",
            }
            ok, msg = CommercialService.create_commercial_product(
                company_db_name, form_data, creator_email, rif=rif
            )
            if ok:
                created += 1
                db['products'].update_one({"sku": sku}, {"$set": {"image_url": image_url}})
            else:
                print(f"  ! {sku}: {msg}")

    print(f"\nCatálogo de prueba creado: {created} producto(s) "
          f"({len(base_products)} artículos FakeStore x {len(VARIANT_SUFFIXES)} variantes).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_fakestore_catalog.py <company_db_name>")
        sys.exit(1)
    run(sys.argv[1])
