# backend/services/login_service.py
from datetime import datetime
from werkzeug.security import check_password_hash
from neon_database import get_neon_connection
from database import client  # Cliente global de MongoDB Atlas

def login_business_user(email, password):
    neon_conn = None
    try:
        neon_conn = get_neon_connection()
        if not neon_conn:
            return {"error": "Error de conexión con el servidor central de control."}, 500

        with neon_conn.cursor() as cursor:
            # 1. Consultamos todas las empresas en Neon para buscar a qué MongoDB pertenece este usuario
            cursor.execute("SELECT * FROM businesses")
            all_businesses = cursor.fetchall()

            target_business = None
            user_record = None
            company_db_name = None

            for biz in all_businesses:
                db_name = biz.get("database_name")
                if not db_name:
                    continue
                
                # Conectamos a la BD de MongoDB aislada de esta empresa específica
                company_db = client.get_database(db_name)
                user = company_db['users'].find_one({"email": email})
                
                if user:
                    target_business = biz
                    user_record = user
                    company_db_name = db_name
                    break

            if not user_record or not target_business:
                return {"error": "Credenciales inválidas o usuario no registrado."}, 401

            # 2. Validar contraseña
            if not check_password_hash(user_record["password"], password):
                return {"error": "Credenciales inválidas."}, 401

            # --- 3. VALIDAR ESTADO Y VIGENCIA DE LA LICENCIA EN NEON ---
            rif = target_business.get("rif")
            cursor.execute("SELECT * FROM licenses WHERE assigned_rif = %s", (rif,))
            license_record = cursor.fetchone()

            current_time = datetime.utcnow()
            is_suspended = target_business.get("status") == "suspended"

            # Si hay registro de licencia, verificamos fecha de expiración
            if license_record and license_record.get("expires_at"):
                expires_at = license_record.get("expires_at")
                
                if expires_at < current_time:
                    # La licencia ha expirado -> Actualizar estatus a suspendido en Neon
                    cursor.execute(
                        "UPDATE businesses SET status = 'suspended' WHERE id = %s",
                        (target_business.get("id"),)
                    )
                    neon_conn.commit()
                    return {
                        "error": "Su licencia ha expirado. El acceso se encuentra suspendido. Por favor, realice el pago de la renovación mensual para reactivar el sistema."
                    }, 403

            if is_suspended:
                return {
                    "error": "La cuenta de esta empresa se encuentra suspendida por falta de renovación de licencia."
                }, 403

            # 4. Retornar los datos de sesión limpios
            return {
                "success": True,
                "message": "Inicio de sesión exitoso.",
                "user": {
                    "name": user_record.get("name", "Usuario"),
                    "email": user_record["email"],
                    "role": user_record.get("role", "admin"),
                    "rif": rif,
                    "business_name": target_business.get("name"),
                    "company_db": company_db_name  # ¡Clave para el multi-tenant!
                }
            }, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error interno en el servidor: {str(e)}"}, 500
    finally:
        if neon_conn:
            neon_conn.close()