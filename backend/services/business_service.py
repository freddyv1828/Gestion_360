# backend/services/business_service.py
import os
import re
import base64
import unicodedata
import logging
import boto3
from botocore.config import Config
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from database import client, get_central_db
from utils import get_r2_client, R2_BUCKET_NAME, R2_PUBLIC_DOMAIN
from services.neon_license_service import validate_license_in_neon, mark_license_used_in_neon

# Configuración de Logging
logger = logging.getLogger(__name__)

def register_business_logic(data):
    uploaded_object_keys = []  # Para seguimiento en caso de rollback de archivos si fuera necesario
    
    try:
        activation_token = data.get("activationToken", "").strip()
        name = data.get("name", "").strip()
        rif = data.get("rif", "").strip()
        tax_right = data.get("taxRight", "").strip()
        fiscal_direction = data.get("fiscalDirection", "").strip()
        phone = data.get("phone", "").strip()
        plan_type = data.get("planType", "free")

        # Datos del usuario Admin inicial
        admin_name = data.get("adminName", "").strip()
        admin_email = data.get("adminEmail", "").strip()
        admin_password = data.get("adminPassword", "").strip()

        # Validar campos obligatorios básicos
        if not all([activation_token, name, rif, admin_email, admin_password]):
            return {"error": "Faltan campos obligatorios para completar el registro."}, 400

        # Validar formato RIF (Venezolano: V, E, J, P, G seguidos de dígitos)
        rif_regex = r"^[VEJPG]-[0-9]{8}-[0-9]$"
        if not re.match(rif_regex, rif):
            return {"error": "Formato de RIF inválido. Use el formato Ej. J-12345678-9."}, 400

        # --- 1. CONEXIÓN A LA BD CENTRAL EN MONGODB ---
        central_db = client.get_database("gestion360_central")
        businesses_col = central_db["businesses"]

        # --- 2. VALIDAR LICENCIA EN NEON (PostgreSQL) — fuente de verdad real ---
        validation_result = validate_license_in_neon(activation_token)
        if not validation_result.get("valid"):
            return {"error": validation_result.get("error", "Token de activación inválido.")}, 403

        license_record = validation_result.get("license") or {}
        resolved_plan = license_record.get("plan_type", plan_type)

        # --- 3. VERIFICAR SI YA EXISTE LA EMPRESA POR RIF ---
        if businesses_col.find_one({"rif": rif}):
            return {"error": "Ya existe una empresa registrada con este RIF en el sistema."}, 400

        # --- 4. SUBIDA DE ARCHIVOS A CLOUDFLARE R2 ---
        s3 = get_r2_client()
        documents = data.get("documents", {})
        saved_file_urls = {}

        doc_keys_map = {
            "rifFile": "rif_file_url",
            "actaFile": "acta_file_url",
            "mercantilFile": "mercantil_file_url"
        }

        for client_key, db_column in doc_keys_map.items():
            doc_info = documents.get(client_key)
            if doc_info and "base64" in doc_info and "filename" in doc_info:
                file_name = doc_info["filename"]
                
                # Normalizar nombre del archivo para evitar caracteres extraños en S3
                normalized_filename = unicodedata.normalize('NFKD', file_name).encode('ASCII', 'ignore').decode('ASCII')
                normalized_filename = re.sub(r'[^\w\-_\.]', '_', normalized_filename)
                
                object_key = f"companies/{rif}/{normalized_filename}"

                try:
                    base64_data = doc_info["base64"]
                    if "," in base64_data:
                        base64_data = base64_data.split(",")[1]

                    file_bytes = base64.b64decode(base64_data)
                    
                    s3.put_object(
                        Bucket=R2_BUCKET_NAME,
                        Key=object_key,
                        Body=file_bytes,
                        ContentType="application/pdf"
                    )
                    
                    uploaded_object_keys.append(object_key)
                    file_url = f"{R2_PUBLIC_DOMAIN}/{object_key}"
                    saved_file_urls[db_column] = file_url
                except Exception as file_err:
                    logger.error(f"Error subiendo {client_key} a R2: {file_err}")
                    saved_file_urls[db_column] = None
            else:
                saved_file_urls[db_column] = None

        # --- 5. CONFIGURAR BD AISLADA EN MONGODB ATLAS ---
        clean_rif = rif.replace("-", "").lower()
        company_db_name = f"gestion360_{clean_rif}"
        company_db = client.get_database(company_db_name)
        company_users_col = company_db['users']

        # Verificar si el correo ya existe dentro de la BD de esta empresa específica
        if company_users_col.find_one({"email": admin_email}):
            return {"error": "El correo del administrador ya está registrado en el sistema de esta empresa."}, 400

        # --- 6. REGISTRAR EMPRESA EN EL PLANO CENTRAL DE MONGODB ---
        business_doc = {
            "name": name,
            "rif": rif,
            "tax_right": tax_right,
            "fiscal_direction": fiscal_direction,
            "phone": phone,
            "database_name": company_db_name,
            "status": "active",
            "files": saved_file_urls,
            "created_at": datetime.utcnow()
        }
        insert_result = businesses_col.insert_one(business_doc)
        business_id = str(insert_result.inserted_id)

        # --- 7. MARCAR LICENCIA COMO USADA Y ASIGNARLA AL RIF (EN NEON) ---
        duration_days = 365 if resolved_plan == 'pro' else 30
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        mark_ok, mark_err = mark_license_used_in_neon(activation_token, rif, expires_at)
        if not mark_ok:
            logger.warning(f"La empresa {rif} se registró pero no se pudo marcar el token en Neon: {mark_err}")

        # --- 8. CREAR USUARIO ADMIN DENTRO DE LA BASE DE DATOS AISLADA EN MONGODB ---
        hashed_password = generate_password_hash(admin_password)
        admin_user_doc = {
            "business_id": business_id,
            "rif": rif,
            "name": admin_name,
            "email": admin_email,
            "password": hashed_password,
            "role": "admin",
            "created_at": datetime.utcnow()
        }
        company_users_col.insert_one(admin_user_doc)

        # --- 9. REGISTRAR EN EL ÍNDICE GLOBAL CENTRAL PARA LOGIN O(1) ---
        central_db["global_users"].update_one(
            {"email": admin_email.lower()},
            {
                "$set": {
                    "email": admin_email.lower(),
                    "name": admin_name,
                    "password": hashed_password,
                    "user_type": "company_staff",
                    "role": "admin",
                    "rif": rif,
                    "business_name": name,
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

        return {
            "success": True,
            "message": f"Empresa registrada exitosamente. Base de datos aislada configurada ({company_db_name}) y licencia vinculada.",
            "business_id": business_id
        }, 200

    except Exception as e:
        logger.error(f"Error crítico en register_business_logic: {str(e)}", exc_info=True)
        return {"error": f"Error crítico en el servidor: {str(e)}"}, 500