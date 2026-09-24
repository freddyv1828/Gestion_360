import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# String de conexión a Neon proporcionado
NEON_DATABASE_URL = "postgresql://neondb_owner:npg_d8iWZt6FbyRH@ep-holy-sun-b5f1kb7w-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_neon_connection():
    """Establece y retorna una conexión a la base de datos de Neon (PostgreSQL)."""
    try:
        conn = psycopg2.connect(NEON_DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error conectando a Neon PostgreSQL: {e}")
        return None

def validate_license_in_neon(token_value):
    """
    Consulta la tabla 'licenses' en Neon para verificar si el token es válido, 
    no ha sido usado y no ha expirado.
    """
    conn = get_neon_connection()
    if not conn:
        return {"valid": False, "error": "No se pudo conectar al servidor de control de licencias."}
    
    try:
        with conn.cursor() as cursor:
            # Consultar el token en la tabla central de Neon
            cursor.execute(
                "SELECT * FROM licenses WHERE token_key = %s AND is_active = TRUE",
                (token_value,)
            )
            license_row = cursor.fetchone()
            
            if not license_row:
                return {"valid": False, "error": "Token de activación inválido o inactivo."}
            
            # Verificar si ya fue asignado/utilizado
            if license_row.get("assigned_rif") is not None:
                return {"valid": False, "error": "Este token de licencia ya ha sido utilizado por otra empresa."}
            
            # Verificar fecha de expiración si aplica
            expires_at = license_row.get("expires_at")
            if expires_at and expires_at < datetime.utcnow():
                return {"valid": False, "error": "Este token de licencia ha expirado."}
                
            return {"valid": True, "license": license_row}
            
    except Exception as e:
        print(f"Error validando licencia en Neon: {e}")
        return {"valid": False, "error": f"Error interno de validación: {str(e)}"}
    finally:
        conn.close()