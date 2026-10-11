from datetime import datetime
from bson import ObjectId
from database import get_company_db
from utils import json_safe
from services.route_service import RouteService

CLIENT_TYPES = {'fiscal', 'natural'}


class ClientService:

    @staticmethod
    def get_paginated_clients(company_db_name, filters=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        clients_col = db['clients']
        query = {"is_active": {"$ne": False}}

        if filters:
            search = (filters.get('search') or '').strip()
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"rif_cedula": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}}
                ]

            client_type = (filters.get('client_type') or '').strip()
            if client_type in CLIENT_TYPES:
                query["client_type"] = client_type

            credit_min = (filters.get('credit_min') or '').strip()
            credit_max = (filters.get('credit_max') or '').strip()
            if credit_min or credit_max:
                credit_query = {}
                if credit_min:
                    try:
                        credit_query["$gte"] = float(credit_min)
                    except ValueError:
                        pass
                if credit_max:
                    try:
                        credit_query["$lte"] = float(credit_max)
                    except ValueError:
                        pass
                if credit_query:
                    query["credit_limit"] = credit_query

            route_number = (filters.get('route_number') or '').strip()
            if route_number:
                try:
                    query["route_number"] = int(route_number)
                except ValueError:
                    pass

        skip = (page - 1) * per_page
        cursor = clients_col.find(query).sort('name', 1).skip(skip).limit(per_page)
        clients = list(cursor)
        for c in clients:
            c.setdefault('client_type', 'fiscal')
            c.setdefault('credit_limit', 0.0)
            c.setdefault('phone', '')
            c.setdefault('address', '')
            c.setdefault('route_number', None)

        total_count = clients_col.count_documents(query)

        # Enriquecer con el nombre del vendedor dueño de la ruta (una sola
        # consulta extra, no N+1) — para que el directorio muestre de un
        # vistazo de quién es cartera cada cliente.
        route_numbers = {c['route_number'] for c in clients if c.get('route_number') is not None}
        if route_numbers:
            sellers = db['users'].find({"route_number": {"$in": list(route_numbers)}}, {"name": 1, "route_number": 1})
            seller_by_route = {s['route_number']: s.get('name') for s in sellers}
            for c in clients:
                c['seller_name'] = seller_by_route.get(c.get('route_number'))

        return json_safe(clients), total_count

    @staticmethod
    def get_clients_by_route(company_db_name, route_number, search=None):
        """Cartera de un vendedor: todos los clientes activos con su mismo
        route_number. Usada por la app móvil para 'Mis Clientes'."""
        db = get_company_db(company_db_name)
        if db is None:
            return []
        query = {"is_active": {"$ne": False}, "route_number": route_number}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"rif_cedula": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        clients = list(db['clients'].find(query).sort('name', 1))
        return json_safe(clients)

    @staticmethod
    def get_route_number_for_user(company_db_name, email):
        """Dado el email de un vendedor, devuelve su route_number (o None si
        no tiene ruta asignada). Fuente única de verdad de 'de quién es este
        vendedor' — usada para que Clientes, CxC y el Dashboard del vendedor
        definan 'mi cartera' de la misma forma."""
        db = get_company_db(company_db_name)
        if db is None:
            return None
        user = db['users'].find_one({"email": email}, {"route_number": 1})
        return user.get('route_number') if user else None

    @staticmethod
    def get_seller_email_for_route(company_db_name, route_number):
        """Inverso de get_route_number_for_user: dado un route_number, el
        email del vendedor dueño de esa ruta (o None)."""
        db = get_company_db(company_db_name)
        if db is None or route_number is None:
            return None
        user = db['users'].find_one({"route_number": route_number}, {"email": 1})
        return user.get('email') if user else None

    @staticmethod
    def get_client_ids_for_route(company_db_name, route_number):
        """IDs (ObjectId) de todos los clientes activos de una ruta — para
        filtrar facturas/CxC por 'client_id' sin tener que depender de un
        campo de texto libre como 'seller' en la factura."""
        db = get_company_db(company_db_name)
        if db is None or route_number is None:
            return []
        return [c['_id'] for c in db['clients'].find(
            {"is_active": {"$ne": False}, "route_number": route_number}, {"_id": 1}
        )]

    @staticmethod
    def count_active_clients(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return 0
        return db['clients'].count_documents({"is_active": {"$ne": False}})

    @staticmethod
    def get_client(company_db_name, client_id):
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            client = db['clients'].find_one({"_id": ObjectId(client_id)})
        except Exception:
            return None
        return json_safe(client) if client else None

    @staticmethod
    def create_or_update_client(company_db_name, form_data, creator_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        clients_col = db['clients']
        client_id = (form_data.get('client_id') or '').strip()

        name = (form_data.get('name') or '').strip()
        rif_cedula = (form_data.get('rif_cedula') or '').strip()
        client_type = (form_data.get('client_type') or 'fiscal').strip()
        email = (form_data.get('email') or '').strip()
        phone = (form_data.get('phone') or '').strip()
        address = (form_data.get('address') or '').strip()
        # route_number puede llegar como texto (formularios HTML, scripts) o
        # como entero (JSON de la API/app móvil) — se normaliza aquí para que
        # ningún llamador tenga que acordarse de convertirlo a texto primero.
        route_number_raw = form_data.get('route_number')
        route_number_raw = route_number_raw.strip() if isinstance(route_number_raw, str) else route_number_raw

        if not name:
            return False, "El nombre o razón social del cliente es obligatorio."
        if not rif_cedula:
            return False, "El RIF o cédula del cliente es obligatorio."
        if client_type not in CLIENT_TYPES:
            client_type = 'fiscal'

        try:
            credit_limit = float(form_data.get('credit_limit', 0) or 0)
        except ValueError:
            return False, "El límite de crédito debe ser numérico."

        route_number = None
        if route_number_raw:
            try:
                route_number = int(route_number_raw)
            except ValueError:
                return False, "La ruta debe ser un número."

        existing = clients_col.find_one({
            "rif_cedula": rif_cedula,
            **({"_id": {"$ne": ObjectId(client_id)}} if client_id else {})
        })
        if existing:
            return False, f"Ya existe un cliente registrado con el RIF/Cédula {rif_cedula}."

        try:
            if client_id:
                # La ruta de un cliente ya existente NO se toca desde el
                # formulario general de edición: cambiar de ruta es una acción
                # explícita (ClientService.reassign_route), para que un cliente
                # no pueda migrar de vendedor por accidente al editar su
                # teléfono o dirección.
                clients_col.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": {
                        "name": name,
                        "rif_cedula": rif_cedula,
                        "client_type": client_type,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "credit_limit": credit_limit,
                        "updated_at": datetime.utcnow()
                    }}
                )
                return True, f"Cliente '{name}' actualizado con éxito."
            else:
                if route_number is None:
                    return False, "Debe asignar una ruta al cliente."
                if not RouteService.get_route_by_number(company_db_name, route_number):
                    return False, f"La ruta {route_number} no existe. Créala primero desde Rutas."
                clients_col.insert_one({
                    "name": name,
                    "rif_cedula": rif_cedula,
                    "client_type": client_type,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "credit_limit": credit_limit,
                    "route_number": route_number,
                    "is_active": True,
                    "created_by": creator_email,
                    "created_at": datetime.utcnow()
                })
                return True, f"Cliente '{name}' registrado con éxito."
        except Exception as e:
            return False, f"Error al guardar el cliente: {str(e)}"

    @staticmethod
    def reassign_route(company_db_name, client_id, new_route_number_raw, actor_email):
        """Único camino para mover un cliente de ruta una vez creado. Deja
        rastro en `route_history` para poder auditar quién movió a quién y
        cuándo — antes esto se podía hacer sin dejar huella desde cualquier
        edición del cliente."""
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            new_route_number = int(str(new_route_number_raw).strip())
        except (TypeError, ValueError):
            return False, "La ruta debe ser un número."

        route = RouteService.get_route_by_number(company_db_name, new_route_number)
        if not route:
            return False, f"La ruta {new_route_number} no existe. Créala primero desde Rutas."

        try:
            client = db['clients'].find_one({"_id": ObjectId(client_id)})
        except Exception:
            return False, "Cliente no encontrado."
        if not client:
            return False, "Cliente no encontrado."

        previous_route_number = client.get('route_number')
        if previous_route_number == new_route_number:
            return False, f"El cliente ya pertenece a la ruta {new_route_number}."

        db['clients'].update_one(
            {"_id": client['_id']},
            {
                "$set": {"route_number": new_route_number, "updated_at": datetime.utcnow()},
                "$push": {"route_history": {
                    "from_route": previous_route_number,
                    "to_route": new_route_number,
                    "changed_by": actor_email,
                    "changed_at": datetime.utcnow(),
                }},
            }
        )
        return True, f"Cliente '{client.get('name')}' movido de la ruta {previous_route_number} a la ruta {new_route_number}."

    @staticmethod
    def soft_delete_client(company_db_name, client_id):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            result = db['clients'].update_one(
                {"_id": ObjectId(client_id)},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            if result.modified_count > 0:
                return True, "Cliente inactivado correctamente."
            return False, "Cliente no encontrado."
        except Exception as e:
            return False, f"Error al inactivar: {str(e)}"
