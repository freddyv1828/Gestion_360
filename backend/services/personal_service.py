# backend/services/personal_service.py
import re
import unicodedata
from datetime import datetime
from bson import ObjectId
from flask import session
from werkzeug.security import generate_password_hash
from database import get_company_db, get_central_db
from utils import get_r2_client, R2_BUCKET_NAME

def create_employee_service(form_data, files_data, creator_email, company_rif):
    name = form_data.get('name', '').strip()
    email = form_data.get('email', '').strip().lower()
    phone = form_data.get('phone', '').strip()
    dni = form_data.get('dni', '').strip()
    role = form_data.get('role', '').strip()
    raw_password = form_data.get('password', '').strip()

    if not name or not email or not dni:
        return False, "Nombre, correo electrónico y cédula/DNI son obligatorios."

    # Hashing seguro de contraseña para evitar texto plano
    if not raw_password:
        raw_password = f"Gestion360-{dni[-4:]}"
    hashed_password = generate_password_hash(raw_password)

    s3 = get_r2_client()

    def upload_single_file(file_key):
        f = files_data.get(file_key)
        if f and f.filename != '':
            filename = unicodedata.normalize('NFKD', f.filename).encode('ASCII', 'ignore').decode('ASCII')
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            object_key = f"companies/{company_rif}/personal/{dni}/{filename}"

            try:
                file_bytes = f.read()
                content_type = f.content_type or 'application/octet-stream'
                s3.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType=content_type
                )
                return object_key
            except Exception as e:
                print(f"Error subiendo archivo {file_key} a R2: {e}")
                return None
        return None

    photo_key = upload_single_file('photo')
    dni_doc_key = upload_single_file('dni_doc')
    rif_doc_key = upload_single_file('rif_doc')
    cv_doc_key = upload_single_file('cv_doc')

    try:
        company_db_name = session.get('company_db')
        if not company_db_name:
            return False, "No se encontró la base de datos de la empresa en la sesión."

        db = get_company_db(company_db_name)
        users_col = db['users']

        # Verificar si el DNI o correo ya existen en el tenant
        if users_col.find_one({"$or": [{"dni": dni}, {"email": email}]}):
            return False, "El DNI o correo electrónico ya está registrado en el sistema."

        employee_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "dni": dni,
            "role": role,
            "password": hashed_password,
            "photo": photo_key,
            "dni_doc": dni_doc_key,
            "rif_doc": rif_doc_key,
            "cv_doc": cv_doc_key,
            "created_by": creator_email,
            "created_at": datetime.utcnow()
        }

        insert_res = users_col.insert_one(employee_data)
        user_id = str(insert_res.inserted_id)

        # Indexar en el Directorio Global Central para autenticación O(1)
        central_db = get_central_db()
        company_name = session.get('company_name', 'Empresa')
        user_type = "seller" if role.lower() == "seller" else "company_staff"

        central_db["global_users"].update_one(
            {"email": email},
            {
                "$set": {
                    "email": email,
                    "name": name,
                    "password": hashed_password,
                    "user_type": user_type,
                    "role": role,
                    "rif": company_rif,
                    "business_name": company_name,
                    "company_db": company_db_name,
                    "tenant_user_id": user_id,
                    "is_active": True,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        return True, "Personal registrado con éxito y sincronizado en el directorio central."
            
    except Exception as e:
        print(f"🔥 ERROR CRÍTICO AL REGISTRAR EN BD: {e}")
        return False, str(e)

def update_employee_service(user_id, form_data, files_data, modifier_email, company_rif):
    name = form_data.get('name', '').strip()
    email = form_data.get('email', '').strip().lower()
    phone = form_data.get('phone', '').strip()
    dni = form_data.get('dni', '').strip()
    role = form_data.get('role', '').strip()
    raw_password = form_data.get('password', '').strip()

    s3 = get_r2_client()

    def upload_single_file(file_key):
        f = files_data.get(file_key)
        if f and f.filename != '':
            filename = unicodedata.normalize('NFKD', f.filename).encode('ASCII', 'ignore').decode('ASCII')
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            object_key = f"companies/{company_rif}/personal/{dni}/{filename}"

            try:
                file_bytes = f.read()
                content_type = f.content_type or 'application/octet-stream'
                s3.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType=content_type
                )
                return object_key
            except Exception as e:
                print(f"Error subiendo archivo actualizado {file_key} a R2: {e}")
                return None
        return None

    photo_key = upload_single_file('photo')
    dni_doc_key = upload_single_file('dni_doc')
    rif_doc_key = upload_single_file('rif_doc')
    cv_doc_key = upload_single_file('cv_doc')

    try:
        company_db_name = session.get('company_db')
        if not company_db_name:
            return False, "No se encontró la base de datos de la empresa en la sesión."

        db = get_company_db(company_db_name)
        users_col = db['users']

        query_id = ObjectId(user_id) if len(user_id) == 24 else user_id
        current_user = users_col.find_one({"_id": query_id})

        if not current_user:
            return False, "Usuario no encontrado"

        update_values = {
            'name': name,
            'email': email,
            'phone': phone,
            'dni': dni,
            'role': role,
            'photo': photo_key if photo_key else current_user.get('photo'),
            'dni_doc': dni_doc_key if dni_doc_key else current_user.get('dni_doc'),
            'rif_doc': rif_doc_key if rif_doc_key else current_user.get('rif_doc'),
            'cv_doc': cv_doc_key if cv_doc_key else current_user.get('cv_doc'),
            'updated_by': modifier_email,
            'updated_at': datetime.utcnow()
        }

        hashed_password = None
        if raw_password:
            hashed_password = generate_password_hash(raw_password)
            update_values['password'] = hashed_password

        users_col.update_one({"_id": query_id}, {"$set": update_values})

        # Sincronizar en el Directorio Global Central
        central_db = get_central_db()
        user_type = "seller" if role.lower() == "seller" else "company_staff"
        global_update = {
            "name": name,
            "role": role,
            "user_type": user_type,
            "updated_at": datetime.utcnow()
        }
        if hashed_password:
            global_update["password"] = hashed_password

        # Si cambió el email, actualizamos la llave en global_users
        old_email = current_user.get("email", "").lower()
        if old_email and old_email != email:
            central_db["global_users"].delete_one({"email": old_email})
            global_update["email"] = email
            global_update["rif"] = company_rif
            global_update["company_db"] = company_db_name
            global_update["is_active"] = True
            central_db["global_users"].update_one(
                {"email": email},
                {"$set": global_update},
                upsert=True
            )
        else:
            central_db["global_users"].update_one(
                {"email": email},
                {"$set": global_update}
            )

        return True, "Actualizado y sincronizado con éxito"

    except Exception as e:
        print(f"🔥 ERROR CRÍTICO AL ACTUALIZAR EN BD: {e}")
        return False, str(e)