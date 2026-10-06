"""
Orquestador de un solo comando para dejar un entorno de prueba limpio y funcional:
  1. Registra la empresa de prueba + 2 usuarios (Freddy, Monica).
  2. Siembra clientes de ejemplo.
  3. Importa el catálogo FakeStore (con variantes) como inventario real.
  4. Sincroniza la tasa BCV (USD/EUR -> Bs) desde dolarapi.com.
  5. Siembra cupones de descuento de ejemplo.
  6. Siembra un vehículo de ejemplo (para probar el Plan de Carga).

Requiere correrse en un entorno con salida de red hacia MongoDB Atlas
(backend/.env con DATABASE_URL configurado).

Uso:
    cd backend
    source .venv/bin/activate   # o tu entorno virtual
    python scripts/setup_demo_environment.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import seed_business, seed_clients, seed_fakestore_catalog, seed_coupons, seed_logistics
from services.exchange_rate_service import ExchangeRateService


def main():
    print("== 1/6 Registrando empresa de prueba ==")
    company_db_name = seed_business.run()
    if not company_db_name:
        print("Abortado: no se pudo registrar la empresa (revisa el token de licencia).")
        return

    print("\n== 2/6 Sembrando clientes de ejemplo ==")
    seed_clients.run(company_db_name)

    print("\n== 3/6 Importando catálogo de prueba (FakeStore + variantes) ==")
    seed_fakestore_catalog.run(company_db_name)

    print("\n== 4/6 Sincronizando tasa BCV (USD/EUR -> Bs) ==")
    ok, msg = ExchangeRateService.sync_bcv_rates(company_db_name, "seed@gestion360.com")
    print(msg)

    print("\n== 5/6 Sembrando cupones de ejemplo ==")
    seed_coupons.run(company_db_name)

    print("\n== 6/6 Sembrando vehículo de ejemplo ==")
    seed_logistics.run(company_db_name)

    print(f"\nListo. Ingresa con freddy@mail.com / 123456 o monica@mail.com / 123456")
    print(f"BD de la empresa: {company_db_name}")


if __name__ == "__main__":
    main()
