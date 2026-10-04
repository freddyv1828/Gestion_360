import json
from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.commercial_service import CommercialService, _consume_stock_batches, _recompute_stock_by_warehouse
from services.financial_service import FinancialService

INVOICE_STATUSES = {'emitida', 'anulada'}


def _next_invoice_number(db):
    """Genera un correlativo atómico de facturación (FAC-000001, FAC-000002, ...)."""
    counter = db['company_settings'].find_one_and_update(
        {"_id": "config"},
        {"$inc": {"invoice_seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter.get('invoice_seq', 1) if counter else 1
    return f"FAC-{seq:06d}"


class InvoicingService:

    @staticmethod
    def get_paginated_invoices(company_db_name, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        invoices_col = db['invoices']
        total_count = invoices_col.count_documents({})
        skip = (page - 1) * per_page
        invoices = list(invoices_col.find({}).sort('created_at', -1).skip(skip).limit(per_page))
        for inv in invoices:
            inv['_id'] = str(inv['_id'])
        return invoices, total_count

    @staticmethod
    def get_invoice(company_db_name, invoice_id):
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            invoice = db['invoices'].find_one({"_id": ObjectId(invoice_id)})
        except Exception:
            return None
        if invoice:
            invoice['_id'] = str(invoice['_id'])
        return invoice

    @staticmethod
    def create_invoice(company_db_name, form_data, user_email):
        """
        Registra una factura de venta: valida existencia de stock en el almacén de
        despacho, consume inventario por FEFO para cada línea, y guarda el documento
        de la factura con su desglose de IVA. Si se marca cobro inmediato, además
        registra el ingreso en Tesorería.
        Retorna (ok, mensaje, invoice_id_o_None).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None

        client_name = form_data.get('client_name', '').strip()
        client_rif = form_data.get('client_rif', '').strip() or 'S/RIF'
        client_email = form_data.get('client_email', '').strip()
        warehouse_id = form_data.get('warehouse_id', '').strip()
        payment_method = form_data.get('payment_method', 'Contado').strip()
        notes = form_data.get('notes', '').strip()

        if not client_name:
            return False, "El nombre o razón social del cliente es obligatorio.", None
        if not warehouse_id:
            return False, "Debe seleccionar el almacén de despacho.", None

        try:
            raw_items = json.loads(form_data.get('items_json', '[]'))
        except (ValueError, TypeError):
            return False, "Los artículos de la factura contienen datos inválidos.", None

        if not raw_items:
            return False, "La factura debe incluir al menos un artículo.", None

        products_col = db['products']
        resolved_items = []

        # --- Validación previa (sin mutar inventario) ---
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
                return False, "Uno de los artículos de la factura ya no existe.", None

            batches = product.get('batches', [])
            available = sum(
                float(b.get('qty', 0.0)) for b in batches
                if b.get('warehouse_id') == warehouse_id
            )
            if available < quantity:
                return False, f"Stock insuficiente para '{product.get('name')}' en el almacén seleccionado (Disponible: {available}).", None

            unit_price = float(product.get('price', 0.0))
            iva_rate = float(product.get('iva_rate', 16.0))
            line_total = unit_price * quantity
            line_subtotal = line_total / (1 + (iva_rate / 100.0)) if iva_rate else line_total
            line_iva = line_total - line_subtotal

            resolved_items.append({
                "product_id": product['_id'],
                "name": product.get('name'),
                "sku": product.get('sku'),
                "quantity": quantity,
                "unit_price": unit_price,
                "iva_rate": iva_rate,
                "subtotal": round(line_subtotal, 2),
                "iva_amount": round(line_iva, 2),
                "total": round(line_total, 2),
            })

        invoice_number = _next_invoice_number(db)

        # --- Consumo real de inventario por FEFO (ya validado arriba) ---
        for item in resolved_items:
            product = products_col.find_one({"_id": item['product_id']})
            batches = product.get('batches', [])
            ok, err, consumed = _consume_stock_batches(batches, warehouse_id, item['quantity'])
            if not ok:
                return False, f"Error de concurrencia al descontar '{item['name']}': {err}", None

            stock_by_wh = _recompute_stock_by_warehouse(batches)
            total_stock = sum(stock_by_wh.values())
            products_col.update_one(
                {"_id": item['product_id']},
                {"$set": {
                    "batches": batches,
                    "stock_by_warehouse": stock_by_wh,
                    "stock": total_stock,
                    "updated_at": datetime.utcnow()
                }}
            )
            CommercialService._log_movement(
                db, str(item['product_id']), 'SALIDA', item['quantity'], warehouse_id,
                user_email, notes=f"Venta por factura {invoice_number}", consumed_detail=consumed
            )

        subtotal = round(sum(i['subtotal'] for i in resolved_items), 2)
        iva_total = round(sum(i['iva_amount'] for i in resolved_items), 2)
        total = round(sum(i['total'] for i in resolved_items), 2)

        settings = FinancialService.get_company_settings(company_db_name)

        invoice_doc = {
            "invoice_number": invoice_number,
            "client_name": client_name,
            "client_rif": client_rif,
            "client_email": client_email,
            "warehouse_id": warehouse_id,
            "payment_method": payment_method,
            "notes": notes,
            "items": resolved_items,
            "subtotal": subtotal,
            "iva_total": iva_total,
            "total": total,
            "currency": settings.get('base_currency', 'USD'),
            "status": "emitida",
            "user": user_email,
            "created_at": datetime.utcnow()
        }
        result = db['invoices'].insert_one(invoice_doc)

        account_id = form_data.get('account_id', '').strip()
        if account_id:
            FinancialService.register_transaction(company_db_name, {
                "account_id": account_id,
                "type": "COBRO",
                "amount": str(total),
                "counterparty": client_name,
                "reference": invoice_number,
                "notes": f"Cobro automático de factura {invoice_number}"
            }, user_email)

        return True, f"Factura {invoice_number} emitida con éxito por un total de {total:.2f} {invoice_doc['currency']}.", str(result.inserted_id)

    @staticmethod
    def get_sales_summary(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return {"count": 0, "total_sales": 0.0, "total_iva": 0.0}
        cursor = db['invoices'].find({"status": "emitida"})
        count = 0
        total_sales = 0.0
        total_iva = 0.0
        for inv in cursor:
            count += 1
            total_sales += float(inv.get('total', 0.0))
            total_iva += float(inv.get('iva_total', 0.0))
        return {"count": count, "total_sales": total_sales, "total_iva": total_iva}
