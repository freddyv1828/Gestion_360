"""
Validación de licencias/tokens de activación contra la tabla 'licenses' en Neon
(PostgreSQL) — fuente de verdad real del control de licencias comerciales.
El resto del sistema (empresas, usuarios, inventario) vive en MongoDB; solo el
token de activación se valida y se marca como usado aquí.

Tabla esperada en Neon:
    CREATE TABLE licenses (
        token_key TEXT PRIMARY KEY,
        plan_type TEXT DEFAULT 'free',
        is_active BOOLEAN DEFAULT TRUE,
        assigned_rif TEXT,
        expires_at TIMESTAMP
    );
"""
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from config import NEON_DATABASE_URL

logger = logging.getLogger(__name__)


def get_neon_connection():
    """Abre una conexión corta a Neon. Retorna None si no se pudo conectar."""
    if not NEON_DATABASE_URL:
        logger.error("NEON_DATABASE_URL no está configurada en las variables de entorno (.env).")
        return None
    try:
        return psycopg2.connect(NEON_DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=15)
    except Exception as e:
        logger.error(f"Error conectando a Neon PostgreSQL: {e}")
        return None


def _as_utc_naive(dt):
    """Normaliza un datetime (aware o naive) a UTC naive para poder comparar
    sin importar si la columna de Postgres es TIMESTAMP o TIMESTAMPTZ."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def validate_license_in_neon(token_value):
    """
    Consulta la tabla 'licenses' en Neon para verificar si el token es válido,
    no ha sido usado y no ha expirado.
    Retorna {"valid": bool, "error": str|None, "license": dict|None}.
    """
    token_value = (token_value or "").strip()
    if not token_value:
        return {"valid": False, "error": "Token de activación vacío.", "license": None}

    conn = get_neon_connection()
    if not conn:
        return {"valid": False, "error": "No se pudo conectar al servidor de control de licencias (Neon).", "license": None}

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM licenses WHERE token_key = %s AND is_active = TRUE",
                (token_value,)
            )
            license_row = cursor.fetchone()

            if not license_row:
                return {"valid": False, "error": "Token de activación inválido o inactivo.", "license": None}

            if license_row.get("assigned_rif"):
                return {"valid": False, "error": "Este token de licencia ya ha sido utilizado por otra empresa.", "license": None}

            expires_at = _as_utc_naive(license_row.get("expires_at"))
            if expires_at and expires_at < datetime.utcnow():
                return {"valid": False, "error": "Este token de licencia ha expirado.", "license": None}

            return {"valid": True, "error": None, "license": dict(license_row)}
    except Exception as e:
        logger.error(f"Error validando licencia en Neon: {e}")
        return {"valid": False, "error": f"Error interno validando la licencia: {e}", "license": None}
    finally:
        conn.close()


def mark_license_used_in_neon(token_value, rif, expires_at):
    """Marca el token como asignado a un RIF (consumido) en Neon. Retorna (ok, error_o_None)."""
    conn = get_neon_connection()
    if not conn:
        return False, "No se pudo conectar al servidor de control de licencias (Neon) para marcar el token."

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE licenses SET assigned_rif = %s, expires_at = %s WHERE token_key = %s;",
                (rif, expires_at, token_value)
            )
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marcando licencia como usada en Neon: {e}")
        return False, f"Error marcando el token como usado: {e}"
    finally:
        conn.close()


def check_license_status_in_neon(rif):
    """
    Usado en el LOGIN para validar que la licencia de una empresa no haya
    expirado. Retorna {"ok": bool, "error": str|None}. Si no se encuentra
    ninguna licencia asignada a ese RIF, se considera válida (no bloquea
    accesos de empresas registradas antes de este control).
    """
    conn = get_neon_connection()
    if not conn:
        # No se puede validar (Neon caído) — no bloquear el acceso por un
        # problema de infraestructura externo al login en sí.
        return {"ok": True, "error": None}

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM licenses WHERE assigned_rif = %s", (rif,))
            license_row = cursor.fetchone()
            if not license_row:
                return {"ok": True, "error": None}

            expires_at = _as_utc_naive(license_row.get("expires_at"))
            if expires_at and expires_at < datetime.utcnow():
                return {"ok": False, "error": "Su licencia ha expirado. Por favor, realice el pago de renovación para reactivar el sistema."}
            return {"ok": True, "error": None}
    except Exception as e:
        logger.error(f"Error verificando estatus de licencia en Neon: {e}")
        return {"ok": True, "error": None}
    finally:
        conn.close()
