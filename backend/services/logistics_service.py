from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.invoicing_service import InvoicingService

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

    # ---------------------------------------------------------------
    # Plan de Carga (asignación de facturas/pedidos despachados a una ruta)
    # ---------------------------------------------------------------

    @staticmethod
    def _invoice_weight_kg(invoice):
        return sum(
            float(item.get('quantity', 0)) * float(item.get('weight_kg', 0) or 0)
            for item in invoice.get('items', [])
        )

    @staticmethod
    def get_unassigned_invoices(company_db_name, limit=50):
        """Facturas emitidas que todavía no están asignadas a ninguna hoja de ruta."""
        db = get_company_db(company_db_name)
        invoices = list(db['invoices'].find({
            "status": "emitida",
            "logistics_route_id": {"$exists": False}
        }).sort('created_at', -1).limit(limit))
        results = []
        for inv in invoices:
            results.append({
                "_id": str(inv['_id']),
                "invoice_number": inv.get('invoice_number'),
                "client_name": inv.get('client_name'),
                "total": inv.get('total'),
                "currency": inv.get('currency'),
                "weight_kg": round(LogisticsService._invoice_weight_kg(inv), 2),
            })
        return results

    @staticmethod
    def get_route_load_plan(company_db_name, route_id):
        """Devuelve el plan de carga de una ruta: facturas asignadas, peso total y
        porcentaje de uso de la capacidad del vehículo."""
        db = get_company_db(company_db_name)
        try:
            route = db['logistics_routes'].find_one({"_id": ObjectId(route_id)})
        except Exception:
            return None
        if not route:
            return None

        vehicle = db['vehicles'].find_one({"_id": route['vehicle_id']}) if route.get('vehicle_id') else None
        capacity_kg = float(vehicle.get('capacity_kg', 0)) if vehicle else 0.0

        invoice_ids = route.get('invoice_ids', [])
        invoices = list(db['invoices'].find({"_id": {"$in": invoice_ids}})) if invoice_ids else []

        assigned = []
        total_weight = 0.0
        for inv in invoices:
            w = LogisticsService._invoice_weight_kg(inv)
            total_weight += w
            assigned.append({
                "_id": str(inv['_id']),
                "invoice_number": inv.get('invoice_number'),
                "client_name": inv.get('client_name'),
                "total": inv.get('total'),
                "currency": inv.get('currency'),
                "weight_kg": round(w, 2),
            })

        usage_pct = round((total_weight / capacity_kg) * 100, 1) if capacity_kg > 0 else None

        return {
            "route_id": str(route['_id']),
            "route_code": route.get('route_code'),
            "vehicle_plate": route.get('vehicle_plate'),
            "capacity_kg": capacity_kg,
            "total_weight_kg": round(total_weight, 2),
            "usage_pct": usage_pct,
            "over_capacity": capacity_kg > 0 and total_weight > capacity_kg,
            "invoices": assigned,
        }

    @staticmethod
    def attach_invoice_to_route(company_db_name, route_id, invoice_id):
        """Asigna una factura ya emitida a la hoja de ruta para el plan de carga.
        No bloquea por exceso de peso (el vehículo puede hacer varias vueltas) pero
        AVISA en el mensaje si se supera la capacidad declarada del vehículo."""
        db = get_company_db(company_db_name)
        try:
            route = db['logistics_routes'].find_one({"_id": ObjectId(route_id)})
            invoice = db['invoices'].find_one({"_id": ObjectId(invoice_id)})
        except Exception:
            return False, "Ruta o factura no encontrada."

        if not route:
            return False, "Ruta no encontrada."
        if not invoice:
            return False, "Factura no encontrada."
        if invoice.get('logistics_route_id'):
            return False, "Esta factura ya está asignada a una hoja de ruta."
        if route.get('status') not in ('planificada', 'en_curso'):
            return False, f"No se puede asignar carga a una ruta en estado '{route.get('status')}'."

        db['logistics_routes'].update_one(
            {"_id": route['_id']},
            {"$addToSet": {"invoice_ids": invoice['_id']}, "$set": {"updated_at": datetime.utcnow()}}
        )
        db['invoices'].update_one({"_id": invoice['_id']}, {"$set": {"logistics_route_id": route['_id']}})

        plan = LogisticsService.get_route_load_plan(company_db_name, route_id)
        warning = ""
        if plan and plan.get('over_capacity'):
            warning = f" ADVERTENCIA: la carga total ({plan['total_weight_kg']} kg) supera la capacidad del vehículo ({plan['capacity_kg']} kg)."
        return True, f"Factura {invoice.get('invoice_number')} asignada a la ruta '{route.get('route_code')}'.{warning}"

    @staticmethod
    def detach_invoice_from_route(company_db_name, route_id, invoice_id):
        db = get_company_db(company_db_name)
        try:
            route_oid = ObjectId(route_id)
            invoice_oid = ObjectId(invoice_id)
        except Exception:
            return False, "Ruta o factura no válida."

        db['logistics_routes'].update_one(
            {"_id": route_oid},
            {"$pull": {"invoice_ids": invoice_oid}, "$set": {"updated_at": datetime.utcnow()}}
        )
        db['invoices'].update_one({"_id": invoice_oid}, {"$unset": {"logistics_route_id": ""}})
        return True, "Factura removida del plan de carga de la ruta."

    @staticmethod
    def get_route_for_invoice(company_db_name, invoice_id):
        """Resuelve la ruta/vehículo/chofer asignado a una factura (para la Guía de
        Despacho). Retorna None si aún no tiene ruta asignada."""
        db = get_company_db(company_db_name)
        try:
            invoice = db['invoices'].find_one({"_id": ObjectId(invoice_id)}, {"logistics_route_id": 1})
        except Exception:
            return None
        if not invoice or not invoice.get('logistics_route_id'):
            return None

        route = db['logistics_routes'].find_one({"_id": invoice['logistics_route_id']})
        if not route:
            return None
        return {
            "route_code": route.get('route_code'),
            "vehicle_plate": route.get('vehicle_plate'),
            "driver_name": route.get('driver_name'),
            "status": route.get('status', 'planificada'),
            "started_at": route.get('started_at'),
            "completed_at": route.get('completed_at'),
        }

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
        delivered_at = None
        if new_status == 'en_curso':
            update_fields["started_at"] = datetime.utcnow()
            LogisticsService._set_vehicle_status(db, route['vehicle_id'], 'in_route')
        elif new_status in ('completada', 'cancelada'):
            delivered_at = datetime.utcnow()
            update_fields["completed_at"] = delivered_at
            LogisticsService._set_vehicle_status(db, route['vehicle_id'], 'available')

        db['logistics_routes'].update_one({"_id": route['_id']}, {"$set": update_fields})

        # Completar la hoja de despacho es, hoy, el sustituto de "el chofer
        # entregó y envió la confirmación en la app" — dispara el reloj de
        # comisión para todas las facturas que cargaba. Una ruta cancelada NO
        # cuenta como entrega: la mercancía no llegó al cliente.
        delivery_warnings = []
        if new_status == 'completada':
            for invoice_id in route.get('invoice_ids', []):
                ok_mark, msg_mark = InvoicingService.mark_delivered(
                    company_db_name, str(invoice_id), 'sistema:despacho_completado', delivered_at
                )
                if not ok_mark:
                    delivery_warnings.append(msg_mark)

        status_labels = {
            'en_curso': 'activada (despacho en curso)',
            'completada': 'completada',
            'cancelada': 'cancelada',
        }
        message = f"Ruta '{route.get('route_code')}' {status_labels.get(new_status, new_status)}."
        if delivery_warnings:
            message += " Advertencia confirmando entregas: " + " | ".join(delivery_warnings)
        return True, message
