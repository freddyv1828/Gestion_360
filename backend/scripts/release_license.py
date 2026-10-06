"""
Libera un token de licencia en Neon (limpia assigned_rif/expires_at) para poder
reutilizarlo en una nueva corrida de prueba. Úsalo SOLO en entornos de prueba —
en producción un token usado no debería liberarse así.

Uso:
    python scripts/release_license.py TEST-NUEVO-2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_license_service import get_neon_connection


def run(token_key):
    conn = get_neon_connection()
    if not conn:
        print("No se pudo conectar a Neon.")
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM licenses WHERE token_key = %s", (token_key,))
            row = cursor.fetchone()
            if not row:
                print(f"No existe ningún token '{token_key}' en Neon.")
                return
            print(f"Estado actual: assigned_rif={row.get('assigned_rif')}, expires_at={row.get('expires_at')}")

            cursor.execute(
                "UPDATE licenses SET assigned_rif = NULL, expires_at = NULL WHERE token_key = %s;",
                (token_key,)
            )
        conn.commit()
        print(f"Token '{token_key}' liberado — listo para usarse de nuevo.")
    except Exception as e:
        conn.rollback()
        print(f"Error liberando el token: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/release_license.py <token_key>")
        sys.exit(1)
    run(sys.argv[1])
