import os
import re
import unicodedata
import sqlalchemy
from utils import get_r2_client, get_db_connection, R2_BUCKET_NAME

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
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        users_table = sqlalchemy.Table('users', metadata, autoload_with=engine)

        with engine.connect() as connection:
            insert_stmt = users_table.insert().values(
                name=name,
                email=email,
                phone=phone,
                dni=dni,
                role=role,
                password=password,
                photo=photo_key,
                dni_doc=dni_doc_key,
                rif_doc=rif_doc_key,
                cv_doc=cv_doc_key,
                created_by=creator_email
            )
            connection.execute(insert_stmt)
            connection.commit()
            return True, "Personal registrado con éxito"
            
    except sqlalchemy.exc.IntegrityError as e:
        print(f"⚠️ El DNI o correo ya se encuentra registrado: {e}")
        return False, "El DNI o correo electrónico ya está registrado en el sistema."
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
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        users_table = sqlalchemy.Table('users', metadata, autoload_with=engine)

        with engine.connect() as connection:
            select_stmt = sqlalchemy.select(users_table).where(users_table.c.id == user_id)
            current_user = connection.execute(select_stmt).fetchone()

            if not current_user:
                return False, "Usuario no encontrado"

            current_dict = dict(current_user._mapping)

            update_values = {
                'name': name,
                'email': email,
                'phone': phone,
                'dni': dni,
                'role': role,
                'photo': photo_key if photo_key else current_dict.get('photo'),
                'dni_doc': dni_doc_key if dni_doc_key else current_dict.get('dni_doc'),
                'rif_doc': rif_doc_key if rif_doc_key else current_dict.get('rif_doc'),
                'cv_doc': cv_doc_key if cv_doc_key else current_dict.get('cv_doc'),
            }

            if password:
                update_values['password'] = password

            update_stmt = users_table.update().where(users_table.c.id == user_id).values(**update_values)
            connection.execute(update_stmt)
            connection.commit()

            return True, "Actualizado con éxito"

    except sqlalchemy.exc.IntegrityError as e:
        print(f"⚠️ Conflicto de unicidad al actualizar: {e}")
        return False, "El DNI o correo electrónico ya pertenece a otro usuario."
    except Exception as e:
        print(f"🔥 ERROR CRÍTICO AL ACTUALIZAR EN BD: {e}")
        return False, str(e)