import re
import unicodedata
from datetime import datetime
from bson import ObjectId
from database import get_company_db
from utils import get_r2_client, R2_BUCKET_NAME, json_safe
from services.logistics_service import LogisticsService
from services.invoicing_service import InvoicingService


class DeliveryService:
    """
    Backend de la app de entregas del chofer: sus hojas de despacho
    asignadas, el detalle de cada parada (factura + cliente), y la
    confirmación de entrega con foto + firma, que es la fuente de verdad
    real para `invoice.delivered_at` — el reloj de comisión arranca aquí,
    no en un botón manual de oficina.
    """

    @staticmethod
    def _resolve_driver(db, driver_email):
        return db['users'].find_one({"email": driver_email})

    @staticmethod
    def get_driver_routes(company_db_name, driver_email):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        driver = DeliveryService._resolve_driver(db, driver_email)
        if not driver:
            return []
        routes = list(db['logistics_routes'].find(
            {"driver_id": driver['_id'], "status": {"$in": ["planificada", "en_curso"]}}
        ).sort('created_at', -1))
        for r in routes:
            invoice_ids = r.get('invoice_ids', [])
            r['stop_count'] = len(invoice_ids)
            r['delivered_count'] = db['invoices'].count_documents({
                "_id": {"$in": invoice_ids}, "delivered_at": {"$ne": None}
            }) if invoice_ids else 0
        return json_safe(routes)

    @staticmethod
    def get_route_detail(company_db_name, route_id, driver_email):
        db = get_company_db(company_db_name)
        if db is None:
            return None, "Base de datos no disponible."
        driver = DeliveryService._resolve_driver(db, driver_email)
        if not driver:
            return None, "Chofer no encontrado."
        try:
            route = db['logistics_routes'].find_one({"_id": ObjectId(route_id)})
        except Exception:
            return None, "Ruta no encontrada."
        if not route:
            return None, "Ruta no encontrada."
        if route.get('driver_id') != driver['_id']:
            return None, "Esta ruta no está asignada a este chofer."

        invoice_ids = route.get('invoice_ids', [])
        invoices = list(db['invoices'].find({"_id": {"$in": invoice_ids}})) if invoice_ids else []
        client_ids = {inv['client_id'] for inv in invoices if inv.get('client_id')}
        clients_by_id = {}
        if client_ids:
            for c in db['clients'].find({"_id": {"$in": list(client_ids)}}, {"address": 1, "phone": 1}):
                clients_by_id[c['_id']] = c

        stops = []
        for inv in invoices:
            client = clients_by_id.get(inv.get('client_id'), {})
            stops.append({
                "invoice_id": str(inv['_id']),
                "invoice_number": inv.get('invoice_number'),
                "client_name": inv.get('client_name'),
                "client_address": client.get('address', ''),
                "client_phone": client.get('phone', ''),
                "total": inv.get('total'),
                "currency": inv.get('currency', 'USD'),
                "delivered_at": inv.get('delivered_at'),
                "item_count": len(inv.get('items', [])),
            })

        route_info = {
            "_id": route['_id'],
            "route_code": route.get('route_code'),
            "destination": route.get('destination'),
            "status": route.get('status'),
            "stops": stops,
        }
        return json_safe(route_info), None

    @staticmethod
    def _authorize_route_action(db, route_id, driver_email):
        driver = DeliveryService._resolve_driver(db, driver_email)
        if not driver:
            return None, "Chofer no encontrado."
        try:
            route = db['logistics_routes'].find_one({"_id": ObjectId(route_id)})
        except Exception:
            return None, "Ruta no encontrada."
        if not route or route.get('driver_id') != driver['_id']:
            return None, "Esta ruta no está asignada a este chofer."
        return route, None

    @staticmethod
    def start_route(company_db_name, route_id, driver_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        route, err = DeliveryService._authorize_route_action(db, route_id, driver_email)
        if err:
            return False, err
        return LogisticsService.update_route_status(company_db_name, route_id, 'en_curso')

    @staticmethod
    def complete_route(company_db_name, route_id, driver_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        route, err = DeliveryService._authorize_route_action(db, route_id, driver_email)
        if err:
            return False, err
        return LogisticsService.update_route_status(company_db_name, route_id, 'completada')

    @staticmethod
    def _upload_evidence(file, kind, invoice_number):
        if not file or not getattr(file, 'filename', ''):
            return None
        try:
            s3 = get_r2_client()
            filename = unicodedata.normalize('NFKD', file.filename).encode('ASCII', 'ignore').decode('ASCII')
            filename = re.sub(r'[^\w\-_\.]', '_', filename) or kind
            object_key = f"deliveries/{kind}/{invoice_number or 'sf'}/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            file_bytes = file.read()
            content_type = file.content_type or 'application/octet-stream'
            s3.put_object(Bucket=R2_BUCKET_NAME, Key=object_key, Body=file_bytes, ContentType=content_type)
            return object_key
        except Exception as e:
            print(f"Error subiendo evidencia de entrega ({kind}) a R2: {e}")
            return None

    @staticmethod
    def confirm_delivery(company_db_name, invoice_id, driver_email, photo_file, signature_file, notes='', latitude=None, longitude=None):
        """
        Registra la evidencia de entrega (foto + firma) de UNA factura y
        dispara el reloj de comisión vía InvoicingService.mark_delivered.
        Esta confirmación, con evidencia real, tiene prioridad sobre el sello
        automático de "ruta completada": mark_delivered nunca pisa una fecha
        ya puesta, así que si el chofer confirmó la parada 3 el lunes y la
        ruta completa se cierra el martes, la factura 3 conserva el lunes.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        driver = DeliveryService._resolve_driver(db, driver_email)
        if not driver:
            return False, "Chofer no encontrado."
        try:
            invoice = db['invoices'].find_one({"_id": ObjectId(invoice_id)})
        except Exception:
            return False, "Factura no encontrada."
        if not invoice:
            return False, "Factura no encontrada."

        route = None
        if invoice.get('logistics_route_id'):
            route = db['logistics_routes'].find_one({"_id": invoice['logistics_route_id']})
        if not route or route.get('driver_id') != driver['_id']:
            return False, "Esta factura no está asignada a una ruta de este chofer."

        if not photo_file or not getattr(photo_file, 'filename', ''):
            return False, "Debe adjuntar una foto de la entrega."
        if not signature_file or not getattr(signature_file, 'filename', ''):
            return False, "Debe adjuntar la firma del cliente."

        photo_key = DeliveryService._upload_evidence(photo_file, 'foto', invoice.get('invoice_number'))
        signature_key = DeliveryService._upload_evidence(signature_file, 'firma', invoice.get('invoice_number'))
        if not photo_key or not signature_key:
            return False, "No se pudo subir la evidencia de entrega. Intenta de nuevo."

        delivered_at = datetime.utcnow()
        db['deliveries'].insert_one({
            "invoice_id": invoice['_id'],
            "logistics_route_id": route['_id'],
            "driver_email": driver_email,
            "driver_name": driver.get('name'),
            "client_name": invoice.get('client_name'),
            "photo_key": photo_key,
            "signature_key": signature_key,
            "notes": notes,
            "latitude": latitude,
            "longitude": longitude,
            "delivered_at": delivered_at,
            "created_at": delivered_at,
        })

        InvoicingService.mark_delivered(company_db_name, invoice_id, driver_email, delivered_at)
        return True, f"Entrega de la factura {invoice.get('invoice_number')} confirmada con foto y firma."
