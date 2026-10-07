import json
from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.commercial_service import CommercialService
from services.invoicing_service import InvoicingService
from utils import json_safe

ORDER_STATUSES = ['pendiente', 'en_picking', 'listo_facturar', 'facturado', 'anulado']
OPEN_STATUSES = ['pendiente', 'en_picking', 'listo_facturar']
DOC_TYPES = {'factura_fiscal', 'nota_entrega'}


def _next_order_number(db):
    """Genera un correlativo atómico de pedidos (PED-000001, PED-000002, ...)."""
    counter = db['company_settings'].find_one_and_update(
        {"_id": "config"},
        {"$inc": {"order_seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter.get('order_seq', 1) if counter else 1
    return f"PED-{seq:06d}"


class OrderService:

    @staticmethod
    def get_paginated_orders(company_db_name, status=None, filters=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        orders_col = db['orders']
        query = {}
        if status and status != 'all':
            query['status'] = status

        if filters:
            search = (filters.get('search') or '').strip()
            if search:
                query["$or"] = [
                    {"order_number": {"$regex": search, "$options": "i"}},
                    {"client_name": {"$regex": search, "$options": "i"}},
                    {"client_rif": {"$regex": search, "$options": "i"}},
                ]

            warehouse_id = (filters.get('warehouse_id') or '').strip()
            if warehouse_id:
                query['warehouse_id'] = warehouse_id

            date_from = (filters.get('date_from') or '').strip()
            date_to = (filters.get('date_to') or '').strip()
            if date_from or date_to:
                date_query = {}
                if date_from:
                    try:
                        date_query["$gte"] = datetime.strptime(date_from, '%Y-%m-%d')
                    except ValueError:
                        pass
                if date_to:
                    try:
                        date_query["$lte"] = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    except ValueError:
                        pass
                if date_query:
                    query["created_at"] = date_query

        total_count = orders_col.count_documents(query)
        skip = (page - 1) * per_page
        orders = list(orders_col.find(query).sort('created_at', -1).skip(skip).limit(per_page))
        orders = json_safe(orders)
        return orders, total_count

    @staticmethod
    def count_orders(company_db_name, created_by=None, statuses=None):
        db = get_company_db(company_db_name)
        if db is None:
            return 0
        query = {}
        if created_by:
            query['created_by'] = created_by
        if statuses:
            query['status'] = {"$in": list(statuses)}
        return db['orders'].count_documents(query)

    @staticmethod
    def get_status_counts(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return {}
        counts = {s: db['orders'].count_documents({"status": s}) for s in ORDER_STATUSES}
        counts['all'] = db['orders'].count_documents({})
        return counts

    @staticmethod
    def get_order(company_db_name, order_id):
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            order = db['orders'].find_one({"_id": ObjectId(order_id)})
        except Exception:
            return None
        return json_safe(order) if order else None

    @staticmethod
    def create_order(company_db_name, form_data, user_email):
        """
        Crea un Pedido en estado 'pendiente' y BLOQUEA (reserva) la mercancía
        solicitada en el almacén elegido, para que no pueda venderse dos veces
        mientras el pedido se verifica/factura.
        Retorna (ok, mensaje, order_id_o_None).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None

        client_id = form_data.get('client_id', '').strip() or None
        client_name = form_data.get('client_name', '').strip()
        client_rif = form_data.get('client_rif', '').strip() or 'S/RIF'
        client_email = form_data.get('client_email', '').strip()
        warehouse_id = form_data.get('warehouse_id', '').strip()
        doc_type = form_data.get('doc_type', 'factura_fiscal').strip()
        comment = form_data.get('comment', '').strip()

        if not client_name:
            return False, "El nombre o razón social del cliente es obligatorio.", None
        if not warehouse_id:
            return False, "Debe seleccionar el almacén de despacho.", None
        if doc_type not in DOC_TYPES:
            doc_type = 'factura_fiscal'

        try:
            raw_items = json.loads(form_data.get('items_json', '[]'))
        except (ValueError, TypeError):
            return False, "Los artículos del pedido contienen datos inválidos.", None

        if not raw_items:
            return False, "El pedido debe incluir al menos un artículo.", None

        products_col = db['products']
        resolved_items = []
        reservation_items = []

        for item in raw_items:
            product_id = (item or {}).get('product_id', '').strip()
            try:
                quantity = float(item.get('quantity', 0))
            except (TypeError, ValueError):
                return False, "Cantidad inválida en uno de los artículos.", None
            if not product_id or quantity <= 0:
                return False, "Cada línea requiere un artículo y una cantidad mayor a cero.", None

            product = products_col.find_one({"_id": ObjectId(product_id)})
            if not product:
                return False, "Uno de los artículos del pedido ya no existe.", None

            unit_type = product.get('unit_type', 'unidad')
            resolved_items.append({
                "product_id": product['_id'],
                "name": product.get('name'),
                "sku": product.get('sku'),
                "unit_type": unit_type,
                "requires_weighing": unit_type in ('kg', 'litros'),
                "quantity": quantity,
                "unit_price": float(product.get('price', 0.0)),
                "verified": False,
                "verified_quantity": None,
            })
            reservation_items.append({"product_id": product_id, "quantity": quantity})

        ok, msg = CommercialService.reserve_stock_for_order(company_db_name, warehouse_id, reservation_items)
        if not ok:
            return False, msg, None

        order_number = _next_order_number(db)
        order_doc = {
            "order_number": order_number,
            "client_id": ObjectId(client_id) if client_id else None,
            "client_name": client_name,
            "client_rif": client_rif,
            "client_email": client_email,
            "warehouse_id": warehouse_id,
            "doc_type": doc_type,
            "comment": comment,
            "items": resolved_items,
            "status": "pendiente",
            "reserved": True,
            "invoice_id": None,
            "created_by": user_email,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = db['orders'].insert_one(order_doc)
        return True, f"Pedido {order_number} creado. Mercancía bloqueada en el almacén seleccionado.", str(result.inserted_id)

    @staticmethod
    def verify_order_item(company_db_name, order_id, product_id, verified_quantity):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        try:
            order = db['orders'].find_one({"_id": ObjectId(order_id)})
        except Exception:
            return False, "Pedido no encontrado."
        if not order:
            return False, "Pedido no encontrado."
        if order['status'] not in ('pendiente', 'en_picking'):
            return False, "Solo se pueden verificar artículos en pedidos pendientes o en picking."

        try:
            verified_quantity = float(verified_quantity)
        except (TypeError, ValueError):
            return False, "La cantidad verificada debe ser numérica."

        items = order.get('items', [])
        found = False
        for item in items:
            if str(item['product_id']) == str(product_id):
                item['verified'] = True
                item['verified_quantity'] = verified_quantity
                found = True
                break
        if not found:
            return False, "Artículo no encontrado en este pedido."

        new_status = order['status']
        if new_status == 'pendiente':
            new_status = 'en_picking'

        db['orders'].update_one(
            {"_id": order['_id']},
            {"$set": {"items": items, "status": new_status, "updated_at": datetime.utcnow()}}
        )
        return True, "Artículo verificado con éxito."

    @staticmethod
    def mark_ready_to_invoice(company_db_name, order_id):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            order = db['orders'].find_one({"_id": ObjectId(order_id)})
        except Exception:
            return False, "Pedido no encontrado."
        if not order:
            return False, "Pedido no encontrado."
        if order['status'] not in ('pendiente', 'en_picking'):
            return False, "El pedido ya fue facturado o anulado."

        pending_items = [i for i in order.get('items', []) if not i.get('verified')]
        if pending_items:
            names = ", ".join(i['name'] for i in pending_items)
            return False, f"Faltan por verificar: {names}. Confirme existencia/peso antes de continuar."

        db['orders'].update_one(
            {"_id": order['_id']},
            {"$set": {"status": "listo_facturar", "updated_at": datetime.utcnow()}}
        )
        return True, "Pedido listo para facturar."

    @staticmethod
    def cancel_order(company_db_name, order_id, reason=""):
        """Anula el pedido y libera (reincorpora) la mercancía reservada."""
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            order = db['orders'].find_one({"_id": ObjectId(order_id)})
        except Exception:
            return False, "Pedido no encontrado."
        if not order:
            return False, "Pedido no encontrado."
        if order['status'] in ('facturado', 'anulado'):
            return False, f"El pedido ya está '{order['status']}' y no puede anularse."

        if order.get('reserved'):
            items = [{"product_id": str(i['product_id']), "quantity": i['quantity']} for i in order.get('items', [])]
            CommercialService.release_stock_for_order(company_db_name, order['warehouse_id'], items)

        db['orders'].update_one(
            {"_id": order['_id']},
            {"$set": {
                "status": "anulado",
                "reserved": False,
                "cancel_reason": reason,
                "updated_at": datetime.utcnow()
            }}
        )
        return True, f"Pedido {order['order_number']} anulado. Mercancía liberada y reincorporada al disponible."

    @staticmethod
    def convert_order_to_invoice(company_db_name, order_id, user_email, overrides=None):
        """
        Convierte un Pedido verificado en Factura real: libera la reserva (para que el
        consumo FEFO real pueda tomar los lotes físicos) y delega en InvoicingService.
        Si la facturación falla, se vuelve a reservar para no perder el bloqueo.

        `overrides` permite ajustar en el momento de facturar lo que se eligió al
        crear el pedido (tipo de documento, moneda, descuento, cupón, vendedor...),
        tal como se pidió: la elección del pedido es solo una preferencia inicial.

        Retorna (ok, mensaje, invoice_id_o_None).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None
        try:
            order = db['orders'].find_one({"_id": ObjectId(order_id)})
        except Exception:
            return False, "Pedido no encontrado.", None
        if not order:
            return False, "Pedido no encontrado.", None
        if order['status'] not in ('pendiente', 'en_picking', 'listo_facturar'):
            return False, f"El pedido ya está '{order['status']}'.", None

        items_for_release = [{"product_id": str(i['product_id']), "quantity": i['quantity']} for i in order.get('items', [])]

        if order.get('reserved'):
            CommercialService.release_stock_for_order(company_db_name, order['warehouse_id'], items_for_release)

        invoice_form = {
            "client_id": str(order['client_id']) if order.get('client_id') else '',
            "client_name": order['client_name'],
            "client_rif": order['client_rif'],
            "client_email": order.get('client_email', ''),
            "warehouse_id": order['warehouse_id'],
            "payment_method": "Contado",
            "doc_type": order.get('doc_type', 'factura_fiscal'),
            "notes": f"Generada desde Pedido {order['order_number']}. {order.get('comment', '')}".strip(),
            "items_json": json.dumps([
                {"product_id": str(i['product_id']), "quantity": i.get('verified_quantity') or i['quantity']}
                for i in order.get('items', [])
            ]),
        }
        if overrides:
            invoice_form.update({k: v for k, v in overrides.items() if v not in (None, '')})

        ok, msg, invoice_id = InvoicingService.create_invoice(company_db_name, invoice_form, user_email)

        if not ok:
            # Re-reservar para no perder el bloqueo si la facturación real falló.
            CommercialService.reserve_stock_for_order(company_db_name, order['warehouse_id'], items_for_release)
            return False, f"No se pudo facturar el pedido: {msg}", None

        db['orders'].update_one(
            {"_id": order['_id']},
            {"$set": {
                "status": "facturado",
                "reserved": False,
                "invoice_id": ObjectId(invoice_id),
                "updated_at": datetime.utcnow()
            }}
        )
        return True, f"Pedido {order['order_number']} facturado con éxito.", invoice_id
