# backend/services/login_service.py
from datetime import datetime
from werkzeug.security import check_password_hash
from database import client  # Cliente global de MongoDB Atlas

def login_business_user(email, password):
    try:
        # Como estamos en una arquitectura centralizada o basada en una BD principal en MongoDB,
        # buscamos la colección de empresas/negocios y licencias directamente en MongoDB Atlas.
        # Ajusta el nombre de tu base de datos central o de control si es distinta (ej. "gestion360_central").
        central_db = client.get_database("gestion360_central")
        
        businesses_collection = central_db["businesses"]
        licenses_collection = central_db["licenses"]

        # 1. Consultamos todas las empresas para buscar a qué MongoDB/base de datos pertenece este usuario
        all_businesses = list(businesses_collection.find({}))

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

        # --- 3. VALIDAR ESTADO Y VIGENCIA DE LA LICENCIA EN MONGODB ---
        rif = target_business.get("rif")
        license_record = licenses_collection.find_one({"assigned_rif": rif})

        current_time = datetime.utcnow()
        is_suspended = target_business.get("status") == "suspended"

        # Si hay registro de licencia, verificamos fecha de expiración
        if license_record and license_record.get("expires_at"):
            expires_at = license_record.get("expires_at")
            
            if expires_at < current_time:
                # La licencia ha expirado -> Actualizar estatus a suspendido
                businesses_collection.update_one(
                    {"id": target_business.get("id")},
                    {"$set": {"status": "suspended"}}
                )
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