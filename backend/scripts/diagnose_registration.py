"""
Diagnóstico rápido: revisa el estado real del token de licencia en Neon y si la
empresa de prueba ya quedó creada en Mongo, para saber el siguiente paso exacto.

Uso:
    python scripts/diagnose_registration.py TEST-NUEVO-2026 J-40123456-7
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_license_service import get_neon_connection
from database import get_central_db, get_company_db


def run(token_key, rif):
    print(f"== Verificando token '{token_key}' en Neon ==")
    conn = get_neon_connection()
    if not conn:
        print("No se pudo conectar a Neon.")
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM licenses WHERE token_key = %s", (token_key,))
            row = cursor.fetchone()
            if not row:
                print("  No existe ningún registro con ese token_key en Neon.")
            else:
                print(f"  token_key:     {row.get('token_key')}")
                print(f"  plan_type:     {row.get('plan_type')}")
                print(f"  is_active:     {row.get('is_active')}")
                print(f"  assigned_rif:  {row.get('assigned_rif')}")
                print(f"  expires_at:    {row.get('expires_at')}")
    finally:
        conn.close()

    print(f"\n== Verificando si la empresa con RIF '{rif}' ya existe en Mongo ==")
    central_db = get_central_db()
    business = central_db["businesses"].find_one({"rif": rif})
    if business:
        print(f"  YA EXISTE: '{business.get('name')}' -> BD: {business.get('database_name')}, status={business.get('status')}")
        company_db_name = business.get('database_name')
        db = get_company_db(company_db_name)
        admins = list(db['users'].find({}, {"email": 1, "name": 1, "_id": 0}))
        print(f"  Usuarios en esa empresa: {admins}")
        print("\nVEREDICTO: la empresa YA está registrada. No hace falta volver a correr el registro.")
        print(f"  Puedes entrar directo en la web con los usuarios de arriba, y correr el resto de los pasos de seed")
        print(f"  manualmente si hace falta, ej:")
        print(f"    python scripts/seed_clients.py {company_db_name}")
        print(f"    python scripts/seed_fakestore_catalog.py {company_db_name}")
        print(f"    python scripts/seed_coupons.py {company_db_name}")
        print(f"    python scripts/seed_logistics.py {company_db_name}")
    else:
        print("  NO existe ninguna empresa con ese RIF en Mongo.")
        print("\nVEREDICTO: el token se marcó como usado en Neon pero la empresa NO quedó creada en Mongo")
        print("  (probablemente una corrida anterior falló a mitad de camino). Libera el token con:")
        print(f"    python scripts/release_license.py {token_key}")
        print("  y vuelve a correr setup_demo_environment.py")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python scripts/diagnose_registration.py <token_key> <rif>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
