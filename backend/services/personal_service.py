# backend/services/personal_service.py
import re
import unicodedata
from datetime import datetime
from bson import ObjectId
from flask import session
from database import get_company_db
from utils import get_r2_client, R2_BUCKET_NAME

def create_employee_service(form_data, files_data, creator_email, company_rif):
    name = form_data.get('name', '').strip()
    email = form_data.get('email', '').strip()
    phone = form_data.get('phone', '').strip()
    dni = form_data.get('dni', '').strip()
    role = form_data.get('role', '').strip()
    password = form_data.get('password', '').strip()

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

        # Verificar si el DNI o correo ya existen
        if users_col.find_one({"$or": [{"dni": dni}, {"email": email}]}):
            return False, "El DNI o correo electrónico ya está registrado en el sistema."

        employee_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "dni": dni,
            "role": role,
            "password": password,
            "photo": photo_key,
            "dni_doc": dni_doc_key,
            "rif_doc": rif_doc_key,
            "cv_doc": cv_doc_key,
            "created_by": creator_email,
            "created_at": datetime.utcnow()
        }

        users_col.insert_one(employee_data)
        return True, "Personal registrado con éxito"
            
    except Exception as e:
        print(f"🔥 ERROR CRÍTICO AL REGISTRAR EN BD: {e}")
        return False, str(e)

def update_employee_service(user_id, form_data, files_data, modifier_email, company_rif):
    name = form_data.get('name', '').strip()
    email = form_data.get('email', '').strip()
    phone = form_data.get('phone', '').strip()
    dni = form_data.get('dni', '').strip()
    role = form_data.get('role', '').strip()
    password = form_data.get('password', '').strip()

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

        if password:
            update_values['password'] = password

        users_col.update_one({"_id": query_id}, {"$set": update_values})
        return True, "Actualizado con éxito"

    except Exception as e:
        print(f"🔥 ERROR CRÍTICO AL ACTUALIZAR EN BD: {e}")
        return False, str(e)