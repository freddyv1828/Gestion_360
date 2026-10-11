# backend/services/personal_service.py
import re
import unicodedata
from datetime import datetime
from bson import ObjectId
from flask import session
from werkzeug.security import generate_password_hash
from database import get_company_db, get_central_db
from utils import get_r2_client, R2_BUCKET_NAME
from services.route_service import RouteService
from services.commercial_service import CommercialService

def create_employee_service(form_data, files_data, creator_email, company_rif):
    name = form_data.get('name', '').strip()
    email = form_data.get('email', '').strip().lower()
    phone = form_data.get('phone', '').strip()
    dni = form_data.get('dni', '').strip()
    role = form_data.get('role', '').strip()
    raw_password = form_data.get('password', '').strip()
    route_number_raw = form_data.get('route_number', '').strip()
    route_number = None
    if route_number_raw:
        try:
            route_number = int(route_number_raw)
        except ValueError:
            return False, "La ruta debe ser un número."

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

        route_ok, route_err = RouteService.validate_route_available_for_seller(company_db_name, route_number)
        if not route_ok:
            return False, route_err

        employee_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "dni": dni,
            "role": role,
            "route_number": route_number,
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

        if route_number is not None:
            RouteService.sync_route_for_seller(company_db_name, route_number, email, name, creator_email)

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
    route_number_raw = form_data.get('route_number', '').strip()
    route_number = None
    if route_number_raw:
        try:
            route_number = int(route_number_raw)
        except ValueError:
            return False, "La ruta debe ser un número."

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

        route_ok, route_err = RouteService.validate_route_available_for_seller(
            company_db_name, route_number, exclude_user_id=user_id
        )
        if not route_ok:
            return False, route_err

        update_values = {
            'name': name,
            'email': email,
            'phone': phone,
            'dni': dni,
            'role': role,
            'route_number': route_number,
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

        if route_number is not None:
            RouteService.sync_route_for_seller(company_db_name, route_number, email, name, modifier_email)
        elif current_user.get('route_number') is not None:
            RouteService.release_seller_route(company_db_name, current_user.get('email', email))

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


DEMO_ROUTE_COUNT = 8
DEMO_CLIENT_TARGET = 40
DEMO_SELLER_PASSWORD = "Vendedor360!"

DEMO_ROUTE_META = {
    1: {"name": "Ruta Centro", "zone": "Casco central"},
    2: {"name": "Ruta Norte", "zone": "Zona norte / industrial"},
    3: {"name": "Ruta Sur", "zone": "Zona sur / residencial"},
    4: {"name": "Ruta Este", "zone": "Zona este"},
    5: {"name": "Ruta Oeste", "zone": "Zona oeste"},
    6: {"name": "Ruta Mayorista A", "zone": "Grandes cuentas / mayoristas 1"},
    7: {"name": "Ruta Mayorista B", "zone": "Grandes cuentas / mayoristas 2"},
    8: {"name": "Ruta Periferia", "zone": "Zonas rurales / periféricas"},
}

DEMO_SELLERS = [
    {"name": "Carlos Ramírez", "email": "vendedor1.ruta1@demo.gestion360.app", "dni": "V-20111001"},
    {"name": "María Fernández", "email": "vendedor2.ruta2@demo.gestion360.app", "dni": "V-20111002"},
    {"name": "José Pérez", "email": "vendedor3.ruta3@demo.gestion360.app", "dni": "V-20111003"},
    {"name": "Ana Torres", "email": "vendedor4.ruta4@demo.gestion360.app", "dni": "V-20111004"},
    {"name": "Luis Gómez", "email": "vendedor5.ruta5@demo.gestion360.app", "dni": "V-20111005"},
    {"name": "Rosa Delgado", "email": "vendedor6.ruta6@demo.gestion360.app", "dni": "V-20111006"},
    {"name": "Miguel Castro", "email": "vendedor7.ruta7@demo.gestion360.app", "dni": "V-20111007"},
    {"name": "Daniela Rojas", "email": "vendedor8.ruta8@demo.gestion360.app", "dni": "V-20111008"},
]

DEMO_CLIENTS = [
    {"name": "Abasto Los Pinos", "rif_cedula": "J-30900001-1", "client_type": "fiscal"},
    {"name": "Panadería El Trigal Dorado", "rif_cedula": "J-30900002-2", "client_type": "fiscal"},
    {"name": "Charcutería La Montañesa", "rif_cedula": "J-30900003-3", "client_type": "fiscal"},
    {"name": "Minimarket San Rafael", "rif_cedula": "J-30900004-4", "client_type": "fiscal"},
    {"name": "Bodegón Mi Tierra", "rif_cedula": "J-30900005-5", "client_type": "fiscal"},
    {"name": "Restaurant El Buen Sabor", "rif_cedula": "J-30900006-6", "client_type": "fiscal"},
    {"name": "Cafetín Doña Carmen", "rif_cedula": "V-15900007", "client_type": "natural"},
    {"name": "Supermercado La Economía", "rif_cedula": "J-30900008-8", "client_type": "fiscal"},
    {"name": "Panadería Dulce Hogar", "rif_cedula": "J-30900009-9", "client_type": "fiscal"},
    {"name": "Abasto La Cosecha", "rif_cedula": "J-30900010-0", "client_type": "fiscal"},
    {"name": "Charcutería El Buen Corte", "rif_cedula": "J-30900011-1", "client_type": "fiscal"},
    {"name": "Minimarket La Esperanza", "rif_cedula": "J-30900012-2", "client_type": "fiscal"},
    {"name": "Bodegón Las Acacias", "rif_cedula": "J-30900013-3", "client_type": "fiscal"},
    {"name": "Restaurant Sazón Criollo", "rif_cedula": "J-30900014-4", "client_type": "fiscal"},
    {"name": "Cafetín Don Pedro", "rif_cedula": "V-15900015", "client_type": "natural"},
    {"name": "Supermercado El Ahorro", "rif_cedula": "J-30900016-6", "client_type": "fiscal"},
    {"name": "Panadería Alba", "rif_cedula": "J-30900017-7", "client_type": "fiscal"},
    {"name": "Abasto San José", "rif_cedula": "J-30900018-8", "client_type": "fiscal"},
    {"name": "Minimarket Las Flores", "rif_cedula": "J-30900019-9", "client_type": "fiscal"},
    {"name": "Bodegón El Trébol", "rif_cedula": "J-30900020-0", "client_type": "fiscal"},
    {"name": "Distribuidora Mayorista El Faro", "rif_cedula": "J-30900021-1", "client_type": "fiscal"},
    {"name": "Hipermercado Caribe", "rif_cedula": "J-30900022-2", "client_type": "fiscal"},
    {"name": "Panadería La Espiga de Oro", "rif_cedula": "J-30900023-3", "client_type": "fiscal"},
    {"name": "Charcutería Europa", "rif_cedula": "J-30900024-4", "client_type": "fiscal"},
    {"name": "Minimarket Girasol", "rif_cedula": "J-30900025-5", "client_type": "fiscal"},
    {"name": "Bodegón Costa Azul", "rif_cedula": "J-30900026-6", "client_type": "fiscal"},
    {"name": "Restaurant La Terraza", "rif_cedula": "J-30900027-7", "client_type": "fiscal"},
    {"name": "Cafetín La Esquina", "rif_cedula": "V-15900028", "client_type": "natural"},
    {"name": "Supermercado Central Plaza", "rif_cedula": "J-30900029-9", "client_type": "fiscal"},
    {"name": "Panadería Monte Real", "rif_cedula": "J-30900030-0", "client_type": "fiscal"},
    {"name": "Distribuidora Mayorista San Marcos", "rif_cedula": "J-30900031-1", "client_type": "fiscal"},
    {"name": "Abasto El Progreso", "rif_cedula": "J-30900032-2", "client_type": "fiscal"},
    {"name": "Charcutería Don Manuel", "rif_cedula": "J-30900033-3", "client_type": "fiscal"},
    {"name": "Minimarket Brisas del Lago", "rif_cedula": "J-30900034-4", "client_type": "fiscal"},
    {"name": "Bodegón La Candelaria", "rif_cedula": "J-30900035-5", "client_type": "fiscal"},
    {"name": "Restaurant El Fogón Criollo", "rif_cedula": "J-30900036-6", "client_type": "fiscal"},
    {"name": "Cafetín Buenos Aires", "rif_cedula": "V-15900037", "client_type": "natural"},
    {"name": "Supermercado Valle Verde", "rif_cedula": "J-30900038-8", "client_type": "fiscal"},
    {"name": "Panadería Nueva Era", "rif_cedula": "J-30900039-9", "client_type": "fiscal"},
    {"name": "Hipermercado Rural del Este", "rif_cedula": "J-30900040-0", "client_type": "fiscal"},
]


def seed_demo_sales_force(company_db_name, creator_email, company_rif, company_name):
    """
    Asegura las DEMO_ROUTE_COUNT rutas comerciales como entidad real (colección
    `routes`), crea (si no existen) un vendedor titular demo por cada una, y
    asegura que existan ~DEMO_CLIENT_TARGET clientes repartidos entre esas
    rutas — asignando ruta primero a los clientes reales que todavía no tengan
    una, y solo creando clientes demo nuevos para completar el resto. También
    siembra un catálogo de productos lácteos demo si el catálogo está vacío.
    Idempotente: correrlo varias veces no duplica rutas, vendedores, clientes
    ni productos ya existentes.
    """
    db = get_company_db(company_db_name)
    if db is None:
        return False, "Base de datos no disponible."

    users_col = db['users']
    clients_col = db['clients']
    central_db = get_central_db()

    for i in range(1, DEMO_ROUTE_COUNT + 1):
        meta = DEMO_ROUTE_META.get(i, {"name": f"Ruta {i}", "zone": ""})
        if not db['routes'].find_one({"number": i}):
            RouteService.create_route(company_db_name, i, meta["name"], meta["zone"], creator_email)

    sellers_created = 0
    sellers_skipped = 0
    for i, seller in enumerate(DEMO_SELLERS, start=1):
        existing = users_col.find_one({"$or": [{"email": seller["email"]}, {"route_number": i, "role": "seller"}]})
        if existing:
            sellers_skipped += 1
            continue

        hashed_password = generate_password_hash(DEMO_SELLER_PASSWORD)
        employee_data = {
            "name": seller["name"],
            "email": seller["email"],
            "phone": "",
            "dni": seller["dni"],
            "role": "seller",
            "route_number": i,
            "password": hashed_password,
            "photo": None,
            "dni_doc": None,
            "rif_doc": None,
            "cv_doc": None,
            "created_by": creator_email,
            "created_at": datetime.utcnow(),
            "is_demo": True,
        }
        insert_res = users_col.insert_one(employee_data)
        sellers_created += 1
        RouteService.sync_route_for_seller(company_db_name, i, seller["email"], seller["name"], creator_email)

        central_db["global_users"].update_one(
            {"email": seller["email"]},
            {
                "$set": {
                    "email": seller["email"],
                    "name": seller["name"],
                    "password": hashed_password,
                    "user_type": "seller",
                    "role": "seller",
                    "rif": company_rif,
                    "business_name": company_name,
                    "company_db": company_db_name,
                    "tenant_user_id": str(insert_res.inserted_id),
                    "is_active": True,
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )

    # 1) Asignar ruta a clientes reales que aún no tengan una (round-robin).
    unrouted = list(clients_col.find({
        "is_active": {"$ne": False},
        "$or": [{"route_number": {"$exists": False}}, {"route_number": None}],
    }))
    clients_routed = 0
    route_cursor = 0
    for client in unrouted:
        route_number = (route_cursor % DEMO_ROUTE_COUNT) + 1
        clients_col.update_one({"_id": client["_id"]}, {"$set": {"route_number": route_number, "updated_at": datetime.utcnow()}})
        route_cursor += 1
        clients_routed += 1

    # 2) Completar hasta DEMO_CLIENT_TARGET clientes creando demo nuevos.
    total_clients = clients_col.count_documents({"is_active": {"$ne": False}})
    clients_created = 0
    for demo_client in DEMO_CLIENTS:
        if total_clients >= DEMO_CLIENT_TARGET:
            break
        if clients_col.find_one({"rif_cedula": demo_client["rif_cedula"]}):
            continue
        route_number = (route_cursor % DEMO_ROUTE_COUNT) + 1
        clients_col.insert_one({
            "name": demo_client["name"],
            "rif_cedula": demo_client["rif_cedula"],
            "client_type": demo_client["client_type"],
            "email": "",
            "phone": "",
            "address": "",
            "credit_limit": 500.0,
            "route_number": route_number,
            "is_active": True,
            "created_by": creator_email,
            "created_at": datetime.utcnow(),
            "is_demo": True,
        })
        route_cursor += 1
        clients_created += 1
        total_clients += 1

    _, catalog_message = CommercialService.seed_demo_catalog(company_db_name, creator_email)

    message = (
        f"Listo: {DEMO_ROUTE_COUNT} ruta(s) comerciales aseguradas, "
        f"{sellers_created} vendedor(es) nuevo(s) creado(s) ({sellers_skipped} ya existían), "
        f"{clients_routed} cliente(s) existente(s) asignado(s) a una ruta, "
        f"{clients_created} cliente(s) demo nuevo(s) creado(s). {catalog_message} "
        f"Contraseña de los vendedores demo: {DEMO_SELLER_PASSWORD}"
    )
    return True, message