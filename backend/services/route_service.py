from datetime import datetime
from bson import ObjectId
from database import get_company_db
from utils import json_safe


class RouteService:
    """
    Rutas comerciales de venta como entidad real (colección `routes`), para que
    Cliente -> Ruta -> Vendedor sea un vínculo anclado y auditable en vez de un
    entero suelto que coincide por casualidad entre `clients.route_number` y
    `users.route_number`. Esta clase es el único camino para crear una ruta,
    asignarle vendedor titular, o reasignar un cliente de ruta — los formularios
    de Clientes y Personal ya no deben escribir `route_number` de reasignación
    libremente (ver ClientService.reassign_route y las validaciones en
    personal_service.py).
    """

    @staticmethod
    def list_routes(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        routes = list(db['routes'].find({}).sort('number', 1))
        for r in routes:
            r['client_count'] = db['clients'].count_documents({
                "route_number": r['number'], "is_active": {"$ne": False}
            })
            seller = None
            if r.get('seller_email'):
                seller = db['users'].find_one({"email": r['seller_email']}, {"name": 1})
            r['seller_name'] = seller.get('name') if seller else None
        return json_safe(routes)

    @staticmethod
    def get_route_by_number(company_db_name, number):
        db = get_company_db(company_db_name)
        if db is None or number is None:
            return None
        return db['routes'].find_one({"number": number})

    @staticmethod
    def create_route(company_db_name, number_raw, name, zone, actor_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None
        try:
            number = int(str(number_raw).strip())
        except (TypeError, ValueError):
            return False, "El número de ruta debe ser un entero.", None
        if number <= 0:
            return False, "El número de ruta debe ser mayor a cero.", None
        name = (name or '').strip()
        if not name:
            return False, "El nombre de la ruta es obligatorio.", None
        if db['routes'].find_one({"number": number}):
            return False, f"Ya existe la ruta {number}.", None

        doc = {
            "number": number,
            "name": name,
            "zone": (zone or '').strip(),
            "seller_email": None,
            "status": "activa",
            "created_by": actor_email,
            "created_at": datetime.utcnow(),
        }
        result = db['routes'].insert_one(doc)
        return True, f"Ruta {number} ('{name}') creada.", str(result.inserted_id)

    @staticmethod
    def validate_route_available_for_seller(company_db_name, route_number, exclude_user_id=None):
        """¿Puede este vendedor quedar como titular de route_number? Falla si
        otro vendedor activo ya es titular de esa ruta. Se usa al crear/editar
        personal para no poder duplicar una ruta entre dos vendedores por
        accidente, que era la causa de deudas visibles para dos vendedores a
        la vez."""
        if route_number is None:
            return True, None
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        query = {"route_number": route_number, "is_active": {"$ne": False}}
        if exclude_user_id:
            try:
                query["_id"] = {"$ne": ObjectId(exclude_user_id)}
            except Exception:
                pass
        holder = db['users'].find_one(query, {"name": 1})
        if holder:
            return False, (
                f"La ruta {route_number} ya tiene un vendedor titular ({holder.get('name')}). "
                f"Para reasignarla, usa la pantalla de Rutas."
            )
        return True, None

    @staticmethod
    def sync_route_for_seller(company_db_name, route_number, seller_email, seller_name, actor_email):
        """Mantiene la colección `routes` Y `users` al día cuando a un
        vendedor se le asigna un route_number (desde el formulario de
        Personal, desde la pantalla de Rutas, o desde el seed demo): crea la
        ruta si no existe, y la marca con este vendedor como titular. Un
        vendedor solo puede ser titular de una ruta a la vez (se le libera
        cualquier otra que tuviera), y una ruta solo puede tener un titular
        (se le quita el route_number en `users` a quien la tuviera antes) —
        sin este segundo paso, dos vendedores podían quedar con el mismo
        route_number en `users` tras una reasignación, y la resolución de
        'dueño de la ruta' (un find_one sin orden garantizado) podía devolver
        al vendedor equivocado."""
        db = get_company_db(company_db_name)
        if db is None or route_number is None:
            return
        db['routes'].update_many(
            {"seller_email": seller_email, "number": {"$ne": route_number}},
            {"$set": {"seller_email": None, "updated_at": datetime.utcnow()}}
        )
        db['users'].update_many(
            {"route_number": route_number, "email": {"$ne": seller_email}},
            {"$set": {"route_number": None, "updated_at": datetime.utcnow()}}
        )

        existing_route = db['routes'].find_one({"number": route_number}, {"seller_email": 1})
        previous_seller_email = existing_route.get('seller_email') if existing_route else None
        history_entry = None
        if previous_seller_email != seller_email:
            history_entry = {
                "from_seller": previous_seller_email,
                "to_seller": seller_email,
                "changed_by": actor_email,
                "changed_at": datetime.utcnow(),
            }

        db['routes'].update_one(
            {"number": route_number},
            {
                "$set": {"seller_email": seller_email, "updated_at": datetime.utcnow()},
                **({"$push": {"history": history_entry}} if history_entry else {}),
                "$setOnInsert": {
                    "name": f"Ruta {route_number}",
                    "zone": "",
                    "status": "activa",
                    "created_by": actor_email,
                    "created_at": datetime.utcnow(),
                },
            },
            upsert=True
        )

    @staticmethod
    def release_seller_route(company_db_name, seller_email):
        """Libera la titularidad de ruta de un vendedor (p.ej. al inactivarlo),
        para que la ruta quede disponible para reasignar sin arrastrar un
        titular fantasma."""
        db = get_company_db(company_db_name)
        if db is None:
            return
        db['routes'].update_many(
            {"seller_email": seller_email},
            {"$set": {"seller_email": None, "updated_at": datetime.utcnow()}}
        )
