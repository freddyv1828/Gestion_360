"""
Ayudante OPCIONAL: solo úsalo si `setup_demo_environment.py` falla con
"Token de activación inválido o inactivo." — significa que ese token_key
todavía no existe en la tabla 'licenses' de Neon (PostgreSQL), que es la
fuente de verdad real del control de licencias. Esto lo crea de forma
idempotente (si ya existe, no lo toca). Requiere NEON_DATABASE_URL en .env.

Uso:
    python scripts/ensure_license.py TEST-NUEVO-2026 --plan pro
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_license_service import get_neon_connection


def run(token_key, plan_type="pro"):
    conn = get_neon_connection()
    if not conn:
        print("No se pudo conectar a Neon. Revisa NEON_DATABASE_URL en backend/.env.")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM licenses WHERE token_key = %s", (token_key,))
            existing = cursor.fetchone()
            if existing:
                print(f"El token '{token_key}' ya existe en Neon (is_active={existing.get('is_active')}, "
                      f"assigned_rif={existing.get('assigned_rif')}). No se modificó nada.")
                return

            cursor.execute(
                """
                INSERT INTO licenses (token_key, plan_type, is_active, assigned_rif, expires_at)
                VALUES (%s, %s, TRUE, NULL, NULL);
                """,
                (token_key, plan_type)
            )
        conn.commit()
        print(f"Token de licencia '{token_key}' creado en Neon (plan={plan_type}). Listo para usarse en el registro.")
    except Exception as e:
        conn.rollback()
        print(f"Error creando el token en Neon: {e}")
        print("¿Existe la tabla 'licenses' en tu base de datos Neon? Debe tener las columnas: "
              "token_key, plan_type, is_active, assigned_rif, expires_at.")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/ensure_license.py <token_key> [--plan free|pro]")
        sys.exit(1)
    token = sys.argv[1]
    plan = "pro"
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    run(token, plan)
