import json
from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.commercial_service import CommercialService, _consume_stock_batches, _recompute_stock_by_warehouse
from services.financial_service import FinancialService
from services.coupon_service import CouponService

INVOICE_STATUSES = {'emitida', 'anulada'}
DOC_TYPES = {'factura_fiscal', 'nota_entrega'}
DISCOUNT_TYPES = {'percentage', 'fixed', ''}


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
    def get_paginated_invoices(company_db_name, filters=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        invoices_col = db['invoices']
        query = {}

        if filters:
            search = (filters.get('search') or '').strip()
            if search:
                query["$or"] = [
                    {"invoice_number": {"$regex": search, "$options": "i"}},
                    {"client_name": {"$regex": search, "$options": "i"}},
                    {"client_rif": {"$regex": search, "$options": "i"}},
                ]

            status = (filters.get('status') or '').strip()
            if status in INVOICE_STATUSES:
                query['status'] = status

            seller = (filters.get('seller') or '').strip()
            if seller:
                query['seller'] = seller

            doc_type = (filters.get('doc_type') or '').strip()
            if doc_type in DOC_TYPES:
                query['doc_type'] = doc_type

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

        total_count = invoices_col.count_documents(query)
        skip = (page - 1) * per_page
        invoices = list(invoices_col.find(query).sort('created_at', -1).skip(skip).limit(per_page))
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
        de la factura con su desglose de IVA, descuento/cupón y moneda.

        Reglas de negocio clave:
        - doc_type='factura_fiscal' -> se desglosa y cobra el IVA configurado por
          producto (comportamiento histórico: el precio de catálogo ya incluye IVA).
        - doc_type='nota_entrega' -> NO se cobra IVA: el cliente paga el subtotal
          (precio sin impuesto), ya que una nota de entrega no es un documento fiscal.
        - El descuento (manual o de cupón) se aplica sobre el subtotal (antes de
          impuesto) y el IVA se recalcula proporcionalmente sobre el subtotal ya
          descontado.
        - Si se indica currency distinta a USD, los montos se convierten con la
          tasa vigente de la empresa (los precios de catálogo son siempre en USD).

        Retorna (ok, mensaje, invoice_id_o_None).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None

        client_id = form_data.get('client_id', '').strip() or None
        client_name = form_data.get('client_name', '').strip()
        client_rif = form_data.get('client_rif', '').strip() or 'S/RIF'
        client_email = form_data.get('client_email', '').strip()
        warehouse_id = form_data.get('warehouse_id', '').strip()
        payment_method = form_data.get('payment_method', 'Contado').strip()
        notes = form_data.get('notes', '').strip()
        seller = form_data.get('seller', '').strip() or user_email
        doc_type = form_data.get('doc_type', 'factura_fiscal').strip()
        currency = (form_data.get('currency', '') or '').strip().upper() or None
        coupon_code = form_data.get('coupon_code', '').strip()
        discount_type = form_data.get('discount_type', '').strip()
        discount_value_raw = form_data.get('discount_value', '').strip()

        if doc_type not in DOC_TYPES:
            doc_type = 'factura_fiscal'
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

        # --- Resolver descuento: cupón tiene prioridad sobre el descuento manual ---
        applied_coupon = None
        if coupon_code:
            ok, err, coupon = CouponService.validate_coupon(company_db_name, coupon_code)
            if not ok:
                return False, err, None
            applied_coupon = coupon
            discount_type = coupon['discount_type']
            try:
                discount_value = float(coupon['discount_value'])
            except (TypeError, ValueError):
                discount_value = 0.0
        else:
            if discount_type not in DISCOUNT_TYPES:
                return False, "Tipo de descuento no válido.", None
            try:
                discount_value = float(discount_value_raw) if discount_value_raw else 0.0
            except ValueError:
                return False, "El valor del descuento debe ser numérico.", None

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
            line_total_with_iva = unit_price * quantity
            line_subtotal = line_total_with_iva / (1 + (iva_rate / 100.0)) if iva_rate else line_total_with_iva

            if doc_type == 'nota_entrega':
                # Nota de entrega: no es documento fiscal, no se cobra IVA.
                line_iva = 0.0
                line_total = line_subtotal
            else:
                line_iva = line_total_with_iva - line_subtotal
                line_total = line_total_with_iva

            resolved_items.append({
                "product_id": product['_id'],
                "name": product.get('name'),
                "sku": product.get('sku'),
                "quantity": quantity,
                "unit_type": product.get('unit_type', 'unidad'),
                "weight_kg": float(product.get('weight_kg', 0) or 0),
                "unit_price": unit_price,
                "iva_rate": iva_rate if doc_type != 'nota_entrega' else 0.0,
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

        subtotal_before_discount = round(sum(i['subtotal'] for i in resolved_items), 2)
        iva_before_discount = round(sum(i['iva_amount'] for i in resolved_items), 2)

        # --- Resolver la moneda final ANTES del descuento: un descuento "fijo" lo
        # ingresa el usuario en la moneda que está viendo en pantalla (la de la
        # factura), pero el subtotal interno siempre está en USD (precios de
        # catálogo) — si no se convierte primero, un descuento de "500" en una
        # factura en VES se restaba como si fueran $500 USD en vez de Bs 500.
        settings = FinancialService.get_company_settings(company_db_name)
        final_currency = currency or settings.get('base_currency', 'USD')

        # --- Aplicar descuento sobre el subtotal (antes de impuesto) ---
        discount_amount = 0.0
        if discount_value > 0 and subtotal_before_discount > 0:
            if discount_type == 'percentage':
                discount_amount = subtotal_before_discount * min(discount_value, 100.0) / 100.0
            elif discount_type == 'fixed':
                discount_value_usd = discount_value
                # Los cupones se configuran una sola vez a nivel de empresa (en USD);
                # solo el descuento manual tecleado en esta factura está en la
                # moneda de la factura y necesita convertirse a USD.
                if not applied_coupon and final_currency != 'USD':
                    converted_discount, _ = FinancialService.convert(company_db_name, discount_value, final_currency, 'USD')
                    if converted_discount is not None:
                        discount_value_usd = converted_discount
                discount_amount = min(discount_value_usd, subtotal_before_discount)
        discount_amount = round(discount_amount, 2)

        subtotal = round(subtotal_before_discount - discount_amount, 2)
        if subtotal_before_discount > 0:
            blended_iva_rate = iva_before_discount / subtotal_before_discount
        else:
            blended_iva_rate = 0.0
        iva_total = round(subtotal * blended_iva_rate, 2) if doc_type != 'nota_entrega' else 0.0
        total = round(subtotal + iva_total, 2)

        # --- Conversión de moneda (catálogo siempre en USD) ---
        exchange_rate_used = None
        if final_currency != 'USD':
            converted_total, exchange_rate_used = FinancialService.convert(company_db_name, total, 'USD', final_currency)
            if converted_total is None:
                return False, f"No hay tasa de cambio definida para {final_currency}. Configure una tasa antes de facturar en esta moneda.", None
            converted_subtotal, _ = FinancialService.convert(company_db_name, subtotal, 'USD', final_currency)
            converted_iva, _ = FinancialService.convert(company_db_name, iva_total, 'USD', final_currency)
        else:
            converted_total, converted_subtotal, converted_iva = total, subtotal, iva_total

        invoice_doc = {
            "invoice_number": invoice_number,
            "client_id": ObjectId(client_id) if client_id else None,
            "client_name": client_name,
            "client_rif": client_rif,
            "client_email": client_email,
            "warehouse_id": warehouse_id,
            "payment_method": payment_method,
            "doc_type": doc_type,
            "seller": seller,
            "notes": notes,
            "items": resolved_items,
            "subtotal_usd": subtotal,
            "iva_total_usd": iva_total,
            "total_usd": total,
            "discount_type": discount_type if discount_value > 0 else None,
            "discount_value": discount_value if discount_value > 0 else 0.0,
            "discount_amount_usd": discount_amount,
            "coupon_code": applied_coupon['code'] if applied_coupon else None,
            "subtotal": round(converted_subtotal, 2),
            "iva_total": round(converted_iva, 2),
            "total": round(converted_total, 2),
            "currency": final_currency,
            "exchange_rate_used": exchange_rate_used,
            "status": "emitida",
            "amount_paid": 0.0 if payment_method == 'Crédito' else round(converted_total, 2),
            "payment_status": 'pendiente' if payment_method == 'Crédito' else 'pagada',
            "user": user_email,
            "created_at": datetime.utcnow()
        }
        result = db['invoices'].insert_one(invoice_doc)

        if applied_coupon:
            CouponService.redeem_coupon(company_db_name, applied_coupon['_id'])

        account_id = form_data.get('account_id', '').strip()
        if account_id:
            FinancialService.register_transaction(company_db_name, {
                "account_id": account_id,
                "type": "COBRO",
                "amount": str(converted_total),
                "counterparty": client_name,
                "reference": invoice_number,
                "notes": f"Cobro automático de factura {invoice_number}"
            }, user_email)

        doc_label = "Factura" if doc_type == 'factura_fiscal' else "Nota de Entrega"
        return True, f"{doc_label} {invoice_number} emitida con éxito por un total de {converted_total:.2f} {final_currency}.", str(result.inserted_id)

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
            total_sales += float(inv.get('total_usd', inv.get('total', 0.0)))
            total_iva += float(inv.get('iva_total_usd', inv.get('iva_total', 0.0)))
        return {"count": count, "total_sales": total_sales, "total_iva": total_iva}
