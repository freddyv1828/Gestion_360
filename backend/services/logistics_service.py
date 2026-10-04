from datetime import datetime
from bson import ObjectId
from database import get_company_db

VEHICLE_STATUSES = {'available', 'in_route', 'maintenance'}
ROUTE_STATUSES = {'planificada', 'en_curso', 'completada', 'cancelada'}


class LogisticsService:

    # ---------------------------------------------------------------
    # Flota de Vehículos
    # ---------------------------------------------------------------

    @staticmethod
    def get_vehicles(company_db_name):
        db = get_company_db(company_db_name)
        vehicles = list(db['vehicles'].find({"is_active": {"$ne": False}}).sort('plate', 1))
        for v in vehicles:
            v['_id'] = str(v['_id'])
            v.setdefault('status', 'available')
        return vehicles

    @staticmethod
    def create_vehicle(company_db_name, form_data):
        db = get_company_db(company_db_name)
        plate = form_data.get('plate', '').strip().upper()
        brand = form_data.get('brand', '').strip()
        model = form_data.get('model', '').strip()
        vehicle_type = form_data.get('type', 'van').strip()

        if not plate:
            return False, "La placa del vehículo es obligatoria."

        try:
            capacity_kg = float(form_data.get('capacity_kg', 0) or 0)
        except ValueError:
            return False, "La capacidad debe ser numérica."

        if db['vehicles'].find_one({"plate": plate}):
            return False, f"Ya existe un vehículo registrado con la placa {plate}."

        db['vehicles'].insert_one({
            "plate": plate,
            "brand": brand,
            "model": model,
            "type": vehicle_type,
            "capacity_kg": capacity_kg,
            "status": "available",
            "is_active": True,
            "created_at": datetime.utcnow()
        })
        return True, f"Vehículo {plate} registrado con éxito."

    @staticmethod
    def _set_vehicle_status(db, vehicle_id, status):
        if status not in VEHICLE_STATUSES:
            return
        db['vehicles'].update_one({"_id": ObjectId(vehicle_id)}, {"$set": {"status": status, "updated_at": datetime.utcnow()}})

    # ---------------------------------------------------------------
    # Choferes (reutiliza el directorio de Personal con role = "Chofer")
    # ---------------------------------------------------------------

    @staticmethod
    def get_available_drivers(company_db_name):
        db = get_company_db(company_db_name)
        drivers = list(db['users'].find({
            "role": {"$regex": "^chofer$", "$options": "i"},
            "is_active": {"$ne": False}
        }).sort('name', 1))
        for d in drivers:
            d['_id'] = str(d['_id'])
        return drivers

    # ---------------------------------------------------------------
    # Rutas y Despachos
    # ---------------------------------------------------------------

    @staticmethod
    def get_routes(company_db_name, page=1, per_page=15):
        db = get_company_db(company_db_name)
        total_count = db['logistics_routes'].count_documents({})
        skip = (page - 1) * per_page
        routes = list(db['logistics_routes'].find({}).sort('created_at', -1).skip(skip).limit(per_page))
        for r in routes:
            r['_id'] = str(r['_id'])
        return routes, total_count

    @staticmethod
    def create_route(company_db_name, form_data, creator_email):
        db = get_company_db(company_db_name)

        route_code = form_data.get('route_code', '').strip() or f"RUTA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        vehicle_id = form_data.get('vehicle_id', '').strip()
        driver_id = form_data.get('driver_id', '').strip()
        destination = form_data.get('destination', '').strip()
        notes = form_data.get('notes', '').strip()

        if not vehicle_id or not driver_id or not destination:
            return False, "Debe seleccionar un vehículo, un chofer y especificar el destino/zona de despacho."

        vehicle = db['vehicles'].find_one({"_id": ObjectId(vehicle_id)})
        if not vehicle:
            return False, "Vehículo no encontrado."
        if vehicle.get('status', 'available') != 'available':
            return False, f"El vehículo {vehicle.get('plate')} no está disponible (estado actual: {vehicle.get('status')})."

        driver = db['users'].find_one({"_id": ObjectId(driver_id)})
        if not driver:
            return False, "Chofer no encontrado."

        db['logistics_routes'].insert_one({
            "route_code": route_code,
            "vehicle_id": vehicle['_id'],
            "vehicle_plate": vehicle.get('plate'),
            "driver_id": driver['_id'],
            "driver_name": driver.get('name'),
            "destination": destination,
            "notes": notes,
            "status": "planificada",
            "created_by": creator_email,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None
        })
        return True, f"Ruta '{route_code}' planificada con éxito."

    @staticmethod
    def update_route_status(company_db_name, route_id, new_status):
        if new_status not in ROUTE_STATUSES:
            return False, "Estado de ruta no válido."

        db = get_company_db(company_db_name)
        route = db['logistics_routes'].find_one({"_id": ObjectId(route_id)})
        if not route:
            return False, "Ruta no encontrada."

        current_status = route.get('status', 'planificada')

        valid_transitions = {
            'planificada': {'en_curso', 'cancelada'},
            'en_curso': {'completada', 'cancelada'},
            'completada': set(),
            'cancelada': set(),
        }
        if new_status not in valid_transitions.get(current_status, set()):
            return False, f"No se puede pasar de '{current_status}' a '{new_status}'."

        update_fields = {"status": new_status, "updated_at": datetime.utcnow()}
        if new_status == 'en_curso':
            update_fields["started_at"] = datetime.utcnow()
            LogisticsService._set_vehicle_status(db, route['vehicle_id'], 'in_route')
        elif new_status in ('completada', 'cancelada'):
            update_fields["completed_at"] = datetime.utcnow()
            LogisticsService._set_vehicle_status(db, route['vehicle_id'], 'available')

        db['logistics_routes'].update_one({"_id": route['_id']}, {"$set": update_fields})

        status_labels = {
            'en_curso': 'activada (despacho en curso)',
            'completada': 'completada',
            'cancelada': 'cancelada',
        }
        return True, f"Ruta '{route.get('route_code')}' {status_labels.get(new_status, new_status)}."
