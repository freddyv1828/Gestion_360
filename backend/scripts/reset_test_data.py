"""
Vacía los datos de prueba (productos, facturas, movimientos, compras, clientes, etc.)
de una empresa específica SIN tocar el código ni borrar la empresa/licencia/usuarios.
Por defecto conserva los almacenes creados (para no tener que recrearlos).

Uso:
    python scripts/reset_test_data.py gestion360_j401234567
    python scripts/reset_test_data.py gestion360_j401234567 --wipe-warehouses
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_company_db

COLLECTIONS_TO_WIPE = [
    'products', 'purchase_orders', 'commercial_movements', 'invoices', 'orders', 'clients',
    'warehouses', 'banking_accounts', 'treasury_transactions', 'exchange_rates',
    'vehicles', 'logistics_routes',
]


def run(company_db_name, keep_warehouses=True):
    db = get_company_db(company_db_name)
    targets = [c for c in COLLECTIONS_TO_WIPE if not (keep_warehouses and c == 'warehouses')]

    for col in targets:
        result = db[col].delete_many({})
        print(f"  {col}: {result.deleted_count} documento(s) eliminado(s).")

    db['company_settings'].update_one(
        {"_id": "config"}, {"$set": {"invoice_seq": 0, "order_seq": 0}}, upsert=True
    )
    print("Listo. invoice_seq/order_seq reiniciados a 0. Empresa, licencia y usuarios NO fueron tocados.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/reset_test_data.py <company_db_name> [--wipe-warehouses]")
        sys.exit(1)
    wipe_wh = "--wipe-warehouses" in sys.argv
    run(sys.argv[1], keep_warehouses=not wipe_wh)
