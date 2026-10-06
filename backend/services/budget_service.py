import json
from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.order_service import OrderService

BUDGET_STATUSES = ['borrador', 'convertido', 'descartado']


def _next_budget_number(db):
    counter = db['company_settings'].find_one_and_update(
        {"_id": "config"},
        {"$inc": {"budget_seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter.get('budget_seq', 1) if counter else 1
    return f"PRE-{seq:06d}"


class BudgetService:
    """
    Presupuestos / Compras Simuladas: una cotización SIN efecto real sobre el
    inventario (no reserva, no bloquea, no descuenta nada) — para que el vendedor
    pueda simular un precio con el cliente antes de comprometerse. Si el cliente
    acepta, se convierte en un Pedido real (y ahí sí se bloquea mercancía).
    """

    @staticmethod
    def get_paginated_budgets(company_db_name, created_by=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0
        query = {}
        if created_by:
            query['created_by'] = created_by
        total_count = db['budgets'].count_documents(query)
        skip = (page - 1) * per_page
        budgets = list(db['budgets'].find(query).sort('created_at', -1).skip(skip).limit(per_page))
        for b in budgets:
            b['_id'] = str(b['_id'])
            if b.get('order_id'):
                b['order_id'] = str(b['order_id'])
        return budgets, total_count

    @staticmethod
    def get_budget(company_db_name, budget_id):
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            budget = db['budgets'].find_one({"_id": ObjectId(budget_id)})
        except Exception:
            return None
        if budget:
            budget['_id'] = str(budget['_id'])
            if budget.get('order_id'):
                budget['order_id'] = str(budget['order_id'])
        return budget

    @staticmethod
    def create_budget(company_db_name, form_data, user_email):
        """
        Simula totales a partir de precios actuales del catálogo, SIN tocar stock.
        Retorna (ok, mensaje, budget_id_o_None).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None

        client_id = form_data.get('client_id', '').strip() or None
        client_name = form_data.get('client_name', '').strip()
        client_rif = form_data.get('client_rif', '').strip() or 'S/RIF'
        comment = form_data.get('comment', '').strip()

        if not client_name:
            return False, "El nombre o razón social del cliente es obligatorio.", None

        try:
            raw_items = json.loads(form_data.get('items_json', '[]'))
        except (ValueError, TypeError):
            return False, "Los artículos del presupuesto contienen datos inválidos.", None
        if not raw_items:
            return False, "El presupuesto debe incluir al menos un artículo.", None

        products_col = db['products']
        resolved_items = []
        subtotal = 0.0

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
                return False, "Uno de los artículos ya no existe en el catálogo.", None

            unit_price = float(product.get('price', 0.0))
            line_total = round(unit_price * quantity, 2)
            subtotal += line_total
            resolved_items.append({
                "product_id": product['_id'],
                "name": product.get('name'),
                "sku": product.get('sku'),
                "quantity": quantity,
                "unit_price": unit_price,
                "total": line_total,
            })

        budget_number = _next_budget_number(db)
        budget_doc = {
            "budget_number": budget_number,
            "client_id": ObjectId(client_id) if client_id else None,
            "client_name": client_name,
            "client_rif": client_rif,
            "comment": comment,
            "items": resolved_items,
            "estimated_total": round(subtotal, 2),
            "status": "borrador",
            "order_id": None,
            "created_by": user_email,
            "created_at": datetime.utcnow(),
        }
        result = db['budgets'].insert_one(budget_doc)
        return True, f"Presupuesto {budget_number} generado (no afecta inventario).", str(result.inserted_id)

    @staticmethod
    def convert_budget_to_order(company_db_name, budget_id, warehouse_id, doc_type, user_email):
        """
        Convierte un presupuesto aceptado por el cliente en un Pedido real — recién
        AHÍ se valida y bloquea la mercancía de verdad.
        Retorna (ok, mensaje, order_id_o_None).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None
        try:
            budget = db['budgets'].find_one({"_id": ObjectId(budget_id)})
        except Exception:
            return False, "Presupuesto no encontrado.", None
        if not budget:
            return False, "Presupuesto no encontrado.", None
        if budget['status'] != 'borrador':
            return False, f"El presupuesto ya está '{budget['status']}'.", None
        if not warehouse_id:
            return False, "Debe seleccionar el almacén de despacho para convertir el presupuesto.", None

        order_form = {
            "client_id": str(budget['client_id']) if budget.get('client_id') else '',
            "client_name": budget['client_name'],
            "client_rif": budget['client_rif'],
            "client_email": "",
            "warehouse_id": warehouse_id,
            "doc_type": doc_type if doc_type in ('factura_fiscal', 'nota_entrega') else 'factura_fiscal',
            "comment": f"Convertido desde Presupuesto {budget['budget_number']}. {budget.get('comment', '')}".strip(),
            "items_json": json.dumps([
                {"product_id": str(i['product_id']), "quantity": i['quantity']} for i in budget.get('items', [])
            ]),
        }

        ok, msg, order_id = OrderService.create_order(company_db_name, order_form, user_email)
        if not ok:
            return False, f"No se pudo convertir el presupuesto: {msg}", None

        db['budgets'].update_one(
            {"_id": budget['_id']},
            {"$set": {"status": "convertido", "order_id": ObjectId(order_id), "updated_at": datetime.utcnow()}}
        )
        return True, f"Presupuesto {budget['budget_number']} convertido en Pedido con éxito.", order_id

    @staticmethod
    def discard_budget(company_db_name, budget_id):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        result = db['budgets'].update_one(
            {"_id": ObjectId(budget_id), "status": "borrador"},
            {"$set": {"status": "descartado", "updated_at": datetime.utcnow()}}
        )
        if result.modified_count > 0:
            return True, "Presupuesto descartado."
        return False, "El presupuesto no existe o ya no está en borrador."
