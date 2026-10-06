"""
Registra la empresa de prueba 'Distribuidora Lácteos Danny, C.A.' usando el token de
activación de licencia ya existente, y crea dos usuarios: Freddy Valero (admin) y
Monica Farias (admin adicional).

Uso:
    python scripts/seed_business.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from werkzeug.security import generate_password_hash
from services.business_service import register_business_logic
from database import get_company_db, get_central_db

COMPANY_DATA = {
    "activationToken": "TEST-NUEVO-2026",
    "name": "Distribuidora Lácteos Danny, C.A.",
    "rif": "J-40123456-7",
    "taxRight": "Contribuyente Ordinario",
    "fiscalDirection": "Av. Principal, Zona Industrial, Venezuela",
    "phone": "0212-1234567",
    "planType": "pro",
    "adminName": "Freddy Valero",
    "adminEmail": "freddy@mail.com",
    "adminPassword": "123456",
    "documents": {}
}

SECOND_STAFF = {
    "name": "Monica Farias",
    "email": "monica@mail.com",
    "password": "123456",
    "role": "admin",
}


def run():
    result, status = register_business_logic(COMPANY_DATA)
    print(f"[register_business_logic] status={status} -> {result}")

    rif = COMPANY_DATA["rif"]
    company_db_name = f"gestion360_{rif.replace('-', '').lower()}"

    if status != 200:
        # Si la empresa ya existía de una corrida anterior, igual continuamos con ese RIF.
        if "Ya existe una empresa registrada" not in str(result.get("error", "")):
            return None
        print("La empresa ya existía — continuando con la BD existente.")

    db = get_company_db(company_db_name)
    central_db = get_central_db()

    email2 = SECOND_STAFF["email"].lower()
    hashed = generate_password_hash(SECOND_STAFF["password"])

    if not db['users'].find_one({"email": email2}):
        db['users'].insert_one({
            "business_id": None,
            "rif": rif,
            "name": SECOND_STAFF["name"],
            "email": email2,
            "password": hashed,
            "role": SECOND_STAFF["role"],
            "created_at": datetime.utcnow()
        })
        print(f"Usuario '{email2}' creado en {company_db_name}.")
    else:
        print(f"Usuario '{email2}' ya existía en {company_db_name}.")

    central_db["global_users"].update_one(
        {"email": email2},
        {
            "$set": {
                "email": email2,
                "name": SECOND_STAFF["name"],
                "password": hashed,
                "user_type": "company_staff",
                "role": SECOND_STAFF["role"],
                "rif": rif,
                "business_name": COMPANY_DATA["name"],
                "company_db": company_db_name,
                "is_active": True,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {"created_at": datetime.utcnow()}
        },
        upsert=True
    )
    print(f"Usuario '{email2}' sincronizado en el directorio global central.")
    print(f"\ncompany_db_name = {company_db_name}")
    return company_db_name


if __name__ == "__main__":
    run()
