# backend/services/login_service.py
from datetime import datetime
from werkzeug.security import check_password_hash
import jwt
from database import client, get_central_db
from config import JWT_SECRET_KEY

def generate_jwt_token(payload, expires_in_days=30):
    """Genera un token JWT para sesiones de la App Móvil o API externa."""
    from datetime import timedelta
    payload_copy = payload.copy()
    payload_copy['exp'] = datetime.utcnow() + timedelta(days=expires_in_days)
    payload_copy['iat'] = datetime.utcnow()
    return jwt.encode(payload_copy, JWT_SECRET_KEY, algorithm='HS256')

def login_business_user(email, password):
    """
    Autenticación O(1) de alto rendimiento utilizando el Directorio Global Central.
    Soporta auto-migración/sincronización transparente de cuentas preexistentes.
    """
    try:
        email_clean = email.strip().lower()
        central_db = get_central_db()
        global_users_col = central_db["global_users"]
        businesses_col = central_db["businesses"]
        licenses_col = central_db["licenses"]

        # 1. Búsqueda O(1) en el Directorio Global Central
        global_user = global_users_col.find_one({"email": email_clean})

        target_business = None
        user_record = None
        company_db_name = None

        if global_user:
            # Usuario ya indexado en el plano central
            user_record = global_user
            company_db_name = global_user.get("company_db")
            rif = global_user.get("rif")

            if rif:
                target_business = businesses_col.find_one({"rif": rif})
        else:
            # Fallback de auto-sincronización para cuentas creadas antes de la refactorización
            all_businesses = list(businesses_col.find({}))
            for biz in all_businesses:
                db_name = biz.get("database_name")
                if not db_name:
                    continue

                tenant_db = client.get_database(db_name)
                found = tenant_db['users'].find_one({"email": {"$regex": f"^{email_clean}$", "$options": "i"}})
                if found:
                    target_business = biz
                    user_record = found
                    company_db_name = db_name

                    # Auto-indexar en el Directorio Global Central para que las futuras consultas sean O(1)
                    user_role = found.get("role", "admin")
                    user_type = "seller" if str(user_role).lower() == "seller" else "company_staff"
                    global_users_col.update_one(
                        {"email": email_clean},
                        {
                            "$set": {
                                "email": email_clean,
                                "name": found.get("name", "Usuario"),
                                "password": found.get("password"),
                                "user_type": user_type,
                                "role": user_role,
                                "rif": biz.get("rif"),
                                "business_name": biz.get("name"),
                                "company_db": company_db_name,
                                "is_active": True,
                                "updated_at": datetime.utcnow()
                            },
                            "$setOnInsert": {
                                "created_at": datetime.utcnow()
                            }
                        },
                        upsert=True
                    )
                    break

        if not user_record:
            return {"error": "Credenciales inválidas o usuario no registrado."}, 401

        # 2. Validación de Contraseña
        stored_hash = user_record.get("password", "")
        if not check_password_hash(stored_hash, password):
            return {"error": "Credenciales inválidas."}, 401

        # 3. Validación de Licencia y Estatus Corporativo (si aplica a personal de empresa)
        rif = user_record.get("rif")
        current_time = datetime.utcnow()

        if target_business:
            # Validar si la empresa está suspendida
            if target_business.get("status") == "suspended":
                return {
                    "error": "La cuenta de esta empresa se encuentra suspendida por falta de renovación de licencia."
                }, 403

            # Validar fecha de expiración en licenses
            license_record = licenses_col.find_one({"assigned_rif": rif})
            if license_record and license_record.get("expires_at"):
                if license_record["expires_at"] < current_time:
                    # Marcar como suspendida en businesses
                    businesses_col.update_one(
                        {"rif": rif},
                        {"$set": {"status": "suspended", "updated_at": current_time}}
                    )
                    return {
                        "error": "Su licencia ha expirado. El acceso se encuentra suspendido. Por favor, realice el pago de renovación para reactivar el sistema."
                    }, 403

        # 4. Construcción de Payload de Sesión y Token JWT
        user_info = {
            "name": user_record.get("name", "Usuario"),
            "email": email_clean,
            "role": user_record.get("role", "admin"),
            "user_type": user_record.get("user_type", "company_staff"),
            "rif": rif,
            "business_name": target_business.get("name") if target_business else user_record.get("business_name", "Gestión 360"),
            "company_db": company_db_name
        }

        token = generate_jwt_token(user_info)

        return {
            "success": True,
            "message": "Inicio de sesión exitoso.",
            "token": token,
            "user": user_info
        }, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error interno en el servidor: {str(e)}"}, 500