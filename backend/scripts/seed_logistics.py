"""
Siembra un vehículo de ejemplo para poder probar el Plan de Carga de inmediato.

Uso:
    python scripts/seed_logistics.py gestion360_j401234567
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.logistics_service import LogisticsService
from database import get_company_db


def run(company_db_name):
    ok, msg = LogisticsService.create_vehicle(company_db_name, {
        "plate": "AB123CD", "brand": "Chevrolet", "model": "NHR",
        "type": "truck", "capacity_kg": "3500",
    })
    print(("  OK  " if ok else "  SKIP") + f" {msg}")

    db = get_company_db(company_db_name)
    if not db['users'].find_one({"role": {"$regex": "^chofer$", "$options": "i"}}):
        db['users'].insert_one({
            "name": "Carlos Rondón",
            "email": "carlos.chofer@mail.com",
            "role": "Chofer",
            "phone": "0416-5551234",
        })
        print("  OK   Chofer 'Carlos Rondón' registrado para pruebas de Logística.")
    else:
        print("  SKIP Ya existe al menos un chofer registrado.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_logistics.py <company_db_name>")
        sys.exit(1)
    run(sys.argv[1])
