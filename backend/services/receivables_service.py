import re
import unicodedata
from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.financial_service import FinancialService
from services.client_service import ClientService
from utils import get_r2_client, R2_BUCKET_NAME

# Métodos de pago que no requieren cruce contra el estado de cuenta bancario
# (no hay nada que buscar en el banco: entran directo como verificados).
NON_BANK_METHODS = {'Efectivo', 'Tarjeta', 'Saldo a Favor del Cliente'}

# Tramos de antigüedad de saldo (días transcurridos desde la fecha de la factura).
AGING_BUCKETS = [
    ("0-7", 0, 7),
    ("8-15", 8, 15),
    ("16-21", 16, 21),
    ("22-30", 22, 30),
    ("31-45", 31, 45),
    ("46+", 46, None),
]


def _bucket_for_days(days):
    for label, lo, hi in AGING_BUCKETS:
        if hi is None:
            if days >= lo:
                return label
        elif lo <= days <= hi:
            return label
    return AGING_BUCKETS[0][0]


class ReceivablesService:
    """
    Cuentas por Cobrar a nivel de FACTURA (no solo agregadas por cliente), con
    antigüedad de saldo y ledger de abonos inmutable (ar_payments) para que
    cobranza pueda auditar exactamente qué factura, de qué vendedor y en qué
    fecha generó cada saldo, y qué abonos se le aplicaron.
    """

    @staticmethod
    def get_invoice_receivables(company_db_name, filters=None):
        db = get_company_db(company_db_name)
        if db is None:
            return []

        query = {"status": "emitida", "payment_method": "Crédito"}
        and_conditions = []
        if filters:
            client_id = (filters.get('client_id') or '').strip()
            if client_id:
                try:
                    query['client_id'] = ObjectId(client_id)
                except Exception:
                    return []

            # "De qué vendedor es esta factura" se decide por DOS vías, porque
            # el campo de texto libre `invoice.seller` depende de que alguien
            # en el backoffice lo haya escrito bien al facturar (a veces queda
            # vacío o con el email del admin que facturó). La fuente
            # estructural y confiable es: el cliente de la factura está en la
            # ruta de ventas de ese vendedor (mismo mecanismo que "Mis
            # Clientes" en la app móvil). Se usan ambas con OR para no perder
            # facturas correctamente atribuidas por texto pero cuyo cliente no
            # tenga ruta asignada.
            seller = (filters.get('seller') or '').strip()
            if seller:
                route_number = ClientService.get_route_number_for_user(company_db_name, seller)
                client_ids_for_route = ClientService.get_client_ids_for_route(company_db_name, route_number) if route_number is not None else []
                seller_or = [{"seller": seller}]
                if client_ids_for_route:
                    seller_or.append({"client_id": {"$in": client_ids_for_route}})
                and_conditions.append(seller_or[0] if len(seller_or) == 1 else {"$or": seller_or})

            search = (filters.get('search') or '').strip()
            if search:
                and_conditions.append({"$or": [
                    {"invoice_number": {"$regex": search, "$options": "i"}},
                    {"client_name": {"$regex": search, "$options": "i"}},
                    {"client_rif": {"$regex": search, "$options": "i"}},
                ]})

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

        if and_conditions:
            query['$and'] = and_conditions

        invoices = list(db['invoices'].find(query))
        now = datetime.utcnow()
        results = []
        for inv in invoices:
            total = float(inv.get('total', 0.0))
            amount_paid = float(inv.get('amount_paid', 0.0))
            balance_due = round(total - amount_paid, 2)
            if balance_due <= 0.01:
                continue
            created_at = inv.get('created_at')
            days = (now - created_at).days if created_at else 0
            bucket = _bucket_for_days(days)
            results.append({
                "invoice_id": str(inv['_id']),
                "invoice_number": inv.get('invoice_number'),
                "client_id": str(inv['client_id']) if inv.get('client_id') else None,
                "client_name": inv.get('client_name'),
                "client_rif": inv.get('client_rif'),
                "seller": inv.get('seller'),
                "created_at": created_at,
                "days_outstanding": days,
                "aging_bucket": bucket,
                "currency": inv.get('currency', 'USD'),
                "total": round(total, 2),
                "amount_paid": round(amount_paid, 2),
                "balance_due": balance_due,
            })

        bucket_filter = (filters or {}).get('bucket')
        if bucket_filter:
            results = [r for r in results if r['aging_bucket'] == bucket_filter]

        results.sort(key=lambda r: r['days_outstanding'], reverse=True)

        # Una sola consulta extra (no N+1) para saber qué clientes tienen
        # saldo a favor disponible, y poder ofrecer "Aplicar Saldo a Favor"
        # directamente desde esta tabla.
        client_ids = {ObjectId(r['client_id']) for r in results if r['client_id']}
        credit_map = {}
        if client_ids:
            for c in db['clients'].find({"_id": {"$in": list(client_ids)}, "credit_balance_usd": {"$gt": 0}}):
                credit_map[str(c['_id'])] = round(c.get('credit_balance_usd', 0.0), 2)
        for r in results:
            r['client_credit_balance_usd'] = credit_map.get(r['client_id'], 0.0)

        return results

    @staticmethod
    def get_aging_summary(company_db_name, filters=None):
        items = ReceivablesService.get_invoice_receivables(company_db_name, filters=filters)
        buckets = {label: {"label": label, "count": 0, "total": 0.0} for label, _, _ in AGING_BUCKETS}
        for r in items:
            buckets[r['aging_bucket']]['count'] += 1
            buckets[r['aging_bucket']]['total'] += r['balance_due']
        for b in buckets.values():
            b['total'] = round(b['total'], 2)
        return {
            "buckets": [buckets[label] for label, _, _ in AGING_BUCKETS],
            "total_balance": round(sum(r['balance_due'] for r in items), 2),
            "total_invoices": len(items),
        }

    @staticmethod
    def get_payments_for_invoice(company_db_name, invoice_id):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        try:
            oid = ObjectId(invoice_id)
        except Exception:
            return []
        payments = list(db['ar_payments'].find({"invoice_id": oid}).sort('created_at', -1))
        for p in payments:
            p['_id'] = str(p['_id'])
            p['invoice_id'] = str(p['invoice_id'])
            p['client_id'] = str(p['client_id']) if p.get('client_id') else None
            p['account_id'] = str(p['account_id']) if p.get('account_id') else None
        return payments

    @staticmethod
    def get_client_statement(company_db_name, client_id):
        """Estado de cuenta completo de un cliente: todas sus facturas a crédito
        y todos los abonos que se le han aplicado — para auditoría total."""
        db = get_company_db(company_db_name)
        if db is None:
            return {"invoices": [], "payments": []}
        try:
            oid = ObjectId(client_id)
        except Exception:
            return {"invoices": [], "payments": []}

        invoices = list(db['invoices'].find(
            {"client_id": oid, "payment_method": "Crédito"}
        ).sort('created_at', -1))
        for inv in invoices:
            inv['_id'] = str(inv['_id'])
            inv['client_id'] = str(inv['client_id']) if inv.get('client_id') else None
            total = float(inv.get('total', 0.0))
            paid = float(inv.get('amount_paid', 0.0))
            inv['amount_paid'] = round(paid, 2)
            inv['balance_due'] = round(total - paid, 2)

        payments = list(db['ar_payments'].find({"client_id": oid}).sort('created_at', -1))
        for p in payments:
            p['_id'] = str(p['_id'])
            p['invoice_id'] = str(p['invoice_id'])
            p['client_id'] = str(p['client_id']) if p.get('client_id') else None
            p['account_id'] = str(p['account_id']) if p.get('account_id') else None

        return {"invoices": invoices, "payments": payments}

    @staticmethod
    def get_payment_inbox(company_db_name, filters=None):
        """
        'Bandeja de Pagos': misma lógica que la Bandeja de Pedidos (Pre-
        Despacho), pero para abonos de CxC. Cruza cada abono contra el estado
        de cuenta bancario REAL ya importado (ReconciliationService) y separa
        los que SÍ se encontraron (verificados, para totalizar y dar por
        buenos) de los que NO (para que cobranza investigue por qué y lo
        corrija). Se recalcula en caliente en cada carga porque el estado de
        cuenta normalmente se importa DESPUÉS de que el vendedor ya registró
        el abono en campo.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return {"verified": [], "unverified": [], "verified_count": 0, "unverified_count": 0, "totals_by_currency": {}}

        # Única fuente de verdad de "¿está verificado?": recalcula TODOS los
        # abonos pendientes (de cualquier filtro) y postea a Tesorería los que
        # ya corresponda, antes de armar la vista filtrada de esta bandeja.
        ReceivablesService._confirm_pending_payments(db, company_db_name)

        filters = filters or {}
        query = {}

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

        seller = (filters.get('seller') or '').strip()
        if seller:
            route_number = ClientService.get_route_number_for_user(company_db_name, seller)
            client_ids_for_route = ClientService.get_client_ids_for_route(company_db_name, route_number) if route_number is not None else []
            seller_or = [{"seller": seller}]
            if client_ids_for_route:
                seller_or.append({"client_id": {"$in": client_ids_for_route}})
            query.update(seller_or[0] if len(seller_or) == 1 else {"$or": seller_or})

        payments = list(db['ar_payments'].find(query).sort('created_at', -1))

        verified, unverified = [], []
        totals_by_currency = {}

        for p in payments:
            method = p.get('payment_method', '')
            stored_value = p.get('reference_verified')
            is_verified = stored_value is True or (stored_value is None and method in NON_BANK_METHODS)

            p['_id'] = str(p['_id'])
            p['invoice_id'] = str(p['invoice_id']) if p.get('invoice_id') else None
            p['client_id'] = str(p['client_id']) if p.get('client_id') else None
            p['account_id'] = str(p['account_id']) if p.get('account_id') else None

            if is_verified:
                verified.append(p)
                cur = p.get('currency', 'USD')
                totals_by_currency[cur] = round(totals_by_currency.get(cur, 0.0) + float(p.get('amount', 0.0)), 2)
            else:
                unverified.append(p)

        return {
            "verified": verified,
            "unverified": unverified,
            "verified_count": len(verified),
            "unverified_count": len(unverified),
            "totals_by_currency": totals_by_currency,
        }

    @staticmethod
    def _confirm_pending_payments(db, company_db_name):
        """Recalcula el estado de verificación de todos los abonos que
        todavía no se han posteado en Tesorería y postea los que ya
        corresponda (sin banco, cruzaron con el estado de cuenta, o alguien
        los verificó manualmente). Es la única fuente de verdad de
        'reference_verified' — se corre antes de mostrar la Bandeja de Pagos
        y también puede llamarse justo después de importar un estado de
        cuenta para que el Centro de Mando se ponga al día de inmediato."""
        # Migración silenciosa y autocontenida: los abonos registrados ANTES
        # de este cambio nunca tuvieron 'treasury_tx_created' porque su
        # movimiento se posteaba siempre de inmediato al registrarse — se
        # marcan como ya posteados para no duplicarlos en Tesorería. Solo
        # toca documentos que JAMÁS tuvieron el campo, así que es segura de
        # correr en cada carga.
        db['ar_payments'].update_many(
            {"treasury_tx_created": {"$exists": False}},
            {"$set": {"treasury_tx_created": True}}
        )

        nc_refs = {m['reference'] for m in db['bank_statement_movements'].find({"bank_type": "NC"}, {"reference": 1}) if m.get('reference')}
        pending = list(db['ar_payments'].find({"treasury_tx_created": {"$ne": True}}))

        for p in pending:
            if p.get('verified_manually') is True:
                is_verified, stored_value = True, True
            else:
                method = p.get('payment_method', '')
                ref = (p.get('reference') or '').strip()
                if method in NON_BANK_METHODS:
                    is_verified, stored_value = True, None
                elif ref:
                    is_verified = ref in nc_refs
                    stored_value = is_verified
                else:
                    is_verified, stored_value = False, False

            if p.get('reference_verified') != stored_value:
                db['ar_payments'].update_one({"_id": p['_id']}, {"$set": {"reference_verified": stored_value}})
                p['reference_verified'] = stored_value

            if is_verified:
                ReceivablesService._post_to_treasury_if_pending(db, company_db_name, p, p.get('user'))

    @staticmethod
    def _post_to_treasury_if_pending(db, company_db_name, payment, user_email):
        """Crea el movimiento de Tesorería (Centro de Mando) para un abono
        que YA está confirmado (no requería banco, su referencia coincide con
        el estado de cuenta importado, o alguien lo verificó manualmente) y
        que todavía no se había reflejado ahí. El Centro de Mando nunca debe
        mostrar un ingreso que todavía no se sabe con certeza si llegó al
        banco — por eso esto se pospone hasta este momento en vez de hacerse
        siempre al registrar el abono."""
        if payment.get('treasury_tx_created'):
            return
        account_id = payment.get('account_id')
        if not account_id:
            return
        notes = payment.get('notes')
        FinancialService.register_transaction(company_db_name, {
            "account_id": str(account_id),
            "type": "COBRO",
            "account_category": "INGRESO POR VENTAS",
            "amount": str(payment.get('amount', 0)),
            "counterparty": payment.get('client_name'),
            "reference": payment.get('reference') or payment.get('invoice_number'),
            "notes": f"Abono a factura {payment.get('invoice_number')}" + (f" — {notes}" if notes else ""),
        }, user_email or payment.get('user') or 'sistema')
        db['ar_payments'].update_one({"_id": payment['_id']}, {"$set": {"treasury_tx_created": True}})
        payment['treasury_tx_created'] = True

    @staticmethod
    def manually_verify_payment(company_db_name, payment_id, user_email):
        """Verificación manual desde la Bandeja de Pagos: para cuando la
        referencia nunca va a cruzar automático (ej. el banco tarda, o el
        cliente se equivocó de referencia pero cobranza confirmó el pago por
        otro medio). Al verificar, también postea el movimiento pendiente en
        Tesorería si tenía cuenta asociada."""
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            payment = db['ar_payments'].find_one({"_id": ObjectId(payment_id)})
        except Exception:
            payment = None
        if not payment:
            return False, "Abono no encontrado."
        if payment.get('reference_verified') is True:
            return False, "Este abono ya estaba verificado."

        db['ar_payments'].update_one(
            {"_id": payment['_id']},
            {"$set": {
                "reference_verified": True,
                "verified_manually": True,
                "verified_by": user_email,
                "verified_at": datetime.utcnow(),
            }}
        )
        payment['reference_verified'] = True
        ReceivablesService._post_to_treasury_if_pending(db, company_db_name, payment, user_email)
        return True, f"Abono de {payment.get('amount')} {payment.get('currency', 'USD')} verificado manualmente y reflejado en Tesorería."

    @staticmethod
    def _resolve_seller(company_db_name, invoice):
        """Vendedor a asociar a un abono/pago para fines de reporte y para la
        Bandeja de Pagos. Se prioriza el dueño REAL de la ruta de ventas del
        cliente (fuente estructural y confiable) sobre el campo de texto
        libre `invoice.seller` (puede quedar vacío o con el email de quien
        facturó, no necesariamente el vendedor real — ver get_invoice_receivables)."""
        client_id = invoice.get('client_id')
        if client_id:
            db = get_company_db(company_db_name)
            client = db['clients'].find_one({"_id": client_id}, {"route_number": 1}) if db is not None else None
            route_number = client.get('route_number') if client else None
            if route_number is not None:
                route_seller = ClientService.get_seller_email_for_route(company_db_name, route_number)
                if route_seller:
                    return route_seller
        return invoice.get('seller')

    @staticmethod
    def _upload_receipt(file, invoice_number):
        """Sube el comprobante/captura del pago (ej. Pago Móvil) a R2, mismo
        patrón de personal_service.upload_single_file."""
        try:
            s3 = get_r2_client()
            filename = unicodedata.normalize('NFKD', file.filename).encode('ASCII', 'ignore').decode('ASCII')
            filename = re.sub(r'[^\w\-_\.]', '_', filename) or 'comprobante'
            object_key = f"receivables/receipts/{invoice_number or 'sf'}/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            file_bytes = file.read()
            content_type = file.content_type or 'application/octet-stream'
            s3.put_object(Bucket=R2_BUCKET_NAME, Key=object_key, Body=file_bytes, ContentType=content_type)
            return object_key
        except Exception as e:
            print(f"Error subiendo comprobante de pago a R2: {e}")
            return None

    @staticmethod
    def register_payment(company_db_name, form_data, user_email, receipt_file=None):
        """
        Registra un abono (parcial o total) sobre una factura a Crédito.
        Dos efectos SIEMPRE atómicos para que la deuda y el libro de abonos
        nunca queden desincronizados:
          1. Inserta un registro inmutable en ar_payments (auditoría: factura,
             cliente, vendedor, monto, método, moneda, fecha, usuario).
          2. Actualiza amount_paid/payment_status en la factura para que el
             saldo pendiente baje de inmediato en todos los reportes.
        Si se indica una cuenta bancaria/billetera, además refleja el cobro en
        Tesorería para que la conciliación bancaria también lo vea.

        Soporta pagar en una moneda distinta a la de la factura (ej. factura
        en USD, cliente paga en VES por Pago Móvil): el monto se convierte a
        la moneda de la factura para aplicarlo, y SIEMPRE se guarda también el
        equivalente en USD y en VES (moneda base y variante) para que CxC se
        pueda leer en ambas sin recalcular. También admite un descuento por
        pronto pago y, si el cliente paga de más, el excedente nunca se
        descarta: pasa a ser saldo a favor del cliente (client_credit_movements
        + clients.credit_balance_usd), disponible para aplicar a futuras
        facturas vía apply_credit_balance().
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        invoice_id = (form_data.get('invoice_id') or '').strip()
        try:
            invoice = db['invoices'].find_one({"_id": ObjectId(invoice_id)})
        except Exception:
            invoice = None
        if not invoice:
            return False, "Factura no encontrada."
        if invoice.get('payment_method') != 'Crédito':
            return False, "Solo se pueden registrar abonos sobre facturas a Crédito."
        if invoice.get('status') != 'emitida':
            return False, "La factura está anulada; no admite abonos."

        try:
            amount = float(form_data.get('amount', 0))
        except (TypeError, ValueError):
            return False, "El monto debe ser numérico."
        if amount <= 0:
            return False, "El monto debe ser mayor a cero."

        invoice_currency = invoice.get('currency', 'USD')
        payment_currency = (form_data.get('currency') or invoice_currency).strip().upper()

        if payment_currency != invoice_currency:
            converted, _ = FinancialService.convert(company_db_name, amount, payment_currency, invoice_currency)
            if converted is None:
                return False, f"No hay tasa de cambio vigente para convertir {payment_currency} a {invoice_currency}."
            amount_in_invoice_currency = converted
        else:
            amount_in_invoice_currency = amount

        total = float(invoice.get('total', 0.0))
        amount_paid = float(invoice.get('amount_paid', 0.0))
        balance_due = round(total - amount_paid, 2)
        if balance_due <= 0.01:
            return False, "Esta factura ya está saldada."

        # Descuento por pronto pago (opcional), calculado sobre el saldo
        # pendiente y siempre normalizado a la moneda de la factura.
        discount_type = (form_data.get('discount_type') or '').strip()
        try:
            discount_value = float(form_data.get('discount_value', 0) or 0)
        except (TypeError, ValueError):
            discount_value = 0.0

        discount_amount = 0.0
        if discount_value > 0 and discount_type in ('percentage', 'fixed'):
            if discount_type == 'percentage':
                discount_amount = balance_due * min(discount_value, 100.0) / 100.0
            else:
                discount_amount = discount_value
                if payment_currency != invoice_currency:
                    converted_discount, _ = FinancialService.convert(company_db_name, discount_value, payment_currency, invoice_currency)
                    if converted_discount is not None:
                        discount_amount = converted_discount
        discount_amount = round(max(discount_amount, 0.0), 2)
        discount_amount = min(discount_amount, balance_due)

        total_applied_raw = round(amount_in_invoice_currency + discount_amount, 2)

        # Sobre-pago: si lo abonado (ya con el descuento sumado) supera el
        # saldo pendiente, el excedente NUNCA se pierde ni se rechaza el
        # abono — se salda la factura por completo y la diferencia se
        # convierte en saldo a favor del cliente.
        excess_in_invoice_currency = round(total_applied_raw - balance_due, 2)
        applied_to_invoice = min(total_applied_raw, balance_due)
        credit_added_usd = 0.0
        if excess_in_invoice_currency > 0.01:
            if invoice_currency == 'USD':
                credit_added_usd = excess_in_invoice_currency
            else:
                converted_excess, _ = FinancialService.convert(company_db_name, excess_in_invoice_currency, invoice_currency, 'USD')
                credit_added_usd = round(converted_excess, 2) if converted_excess is not None else 0.0

        new_amount_paid = round(amount_paid + applied_to_invoice, 2)
        new_balance = round(total - new_amount_paid, 2)
        payment_status = 'pagada' if new_balance <= 0.01 else 'parcial'

        payment_method = (form_data.get('payment_method') or 'Efectivo').strip() or 'Efectivo'
        account_id = (form_data.get('account_id') or '').strip()
        reference = (form_data.get('reference') or '').strip()
        notes = (form_data.get('notes') or '').strip()

        # Equivalentes en moneda base (USD) y variante (VES) del monto
        # REALMENTE pagado (antes de aplicar descuento/exceso), para que CxC
        # siempre se pueda leer en ambas sin importar en qué moneda pagó el
        # cliente.
        amount_usd = amount if payment_currency == 'USD' else None
        if amount_usd is None:
            converted, _ = FinancialService.convert(company_db_name, amount, payment_currency, 'USD')
            amount_usd = round(converted, 2) if converted is not None else None
        amount_ves = amount if payment_currency == 'VES' else None
        if amount_ves is None:
            converted, _ = FinancialService.convert(company_db_name, amount, payment_currency, 'VES')
            amount_ves = round(converted, 2) if converted is not None else None

        # Cotejo contra el estado de cuenta bancario REAL ya importado (ver
        # ReconciliationService): si la referencia que da el cliente coincide
        # con un ingreso (NC) realmente recibido por el banco, el abono queda
        # marcado como verificado — si no, no se bloquea el registro (puede
        # que el banco aún no procese el movimiento), pero queda visible para
        # que cobranza lo revise antes de confiar en el pago.
        reference_verified = None
        if reference:
            bank_match = db['bank_statement_movements'].find_one({"reference": reference, "bank_type": "NC"})
            reference_verified = bank_match is not None

        receipt_image_key = None
        if receipt_file is not None and getattr(receipt_file, 'filename', ''):
            receipt_image_key = ReceivablesService._upload_receipt(receipt_file, invoice.get('invoice_number'))

        payment_seller = ReceivablesService._resolve_seller(company_db_name, invoice)

        payment_doc = {
            "invoice_id": invoice['_id'],
            "invoice_number": invoice.get('invoice_number'),
            "client_id": invoice.get('client_id'),
            "client_name": invoice.get('client_name'),
            "client_rif": invoice.get('client_rif'),
            "seller": payment_seller,
            "amount": amount,
            "currency": payment_currency,
            "amount_usd": amount_usd,
            "amount_ves": amount_ves,
            "discount_type": discount_type if discount_amount > 0 else None,
            "discount_value": discount_value if discount_amount > 0 else 0.0,
            "discount_amount": discount_amount,
            "applied_to_invoice": applied_to_invoice,
            "excess_to_credit_usd": credit_added_usd,
            "payment_method": payment_method,
            "account_id": ObjectId(account_id) if account_id else None,
            "reference": reference,
            "reference_verified": reference_verified,
            "receipt_image_key": receipt_image_key,
            "notes": notes,
            "balance_after": new_balance,
            "user": user_email,
            "created_at": datetime.utcnow(),
            # El Centro de Mando (Tesorería) no debe registrar un ingreso que
            # todavía no se sabe con certeza si llegó al banco: solo se
            # postea de inmediato si el método no requiere banco (efectivo,
            # tarjeta) o si la referencia YA cruzó contra el estado de cuenta
            # importado. Si no, queda pendiente hasta que se confirme
            # (automático al importar el estado de cuenta, o manual desde la
            # Bandeja de Pagos) — así nunca queda "verificándose" en la
            # Bandeja y "ya contado" en Tesorería al mismo tiempo.
            "treasury_tx_created": False,
        }
        should_post_now = account_id and (payment_method in NON_BANK_METHODS or reference_verified is True)

        try:
            db['ar_payments'].insert_one(payment_doc)
            db['invoices'].update_one(
                {"_id": invoice['_id']},
                {"$set": {
                    "amount_paid": new_amount_paid,
                    "payment_status": payment_status,
                    "updated_at": datetime.utcnow(),
                }}
            )
            if credit_added_usd > 0 and invoice.get('client_id'):
                db['clients'].update_one(
                    {"_id": invoice['client_id']},
                    {"$inc": {"credit_balance_usd": credit_added_usd}}
                )
                db['client_credit_movements'].insert_one({
                    "client_id": invoice['client_id'],
                    "client_name": invoice.get('client_name'),
                    "type": "overpayment",
                    "amount_usd": credit_added_usd,
                    "related_invoice_id": invoice['_id'],
                    "related_invoice_number": invoice.get('invoice_number'),
                    "notes": f"Excedente del abono a la factura {invoice.get('invoice_number')}",
                    "user": user_email,
                    "created_at": datetime.utcnow(),
                })
        except Exception as e:
            return False, f"Error al registrar el abono: {str(e)}"

        if should_post_now:
            ReceivablesService._post_to_treasury_if_pending(db, company_db_name, payment_doc, user_email)

        verify_note = ""
        if reference_verified is True:
            verify_note = " Referencia verificada contra el banco ✓."
        elif reference_verified is False:
            verify_note = " Nota: esa referencia todavía no aparece en el último estado de cuenta importado — el movimiento queda pendiente en Tesorería hasta verificarse (automático o manual en la Bandeja de Pagos)."

        discount_note = f" Se aplicó un descuento por pronto pago de {discount_amount:.2f} {invoice_currency}." if discount_amount > 0 else ""
        credit_note = f" El cliente pagó de más: se generó ${credit_added_usd:.2f} de saldo a favor." if credit_added_usd > 0 else ""

        label = "Pago total" if payment_status == 'pagada' else "Abono parcial"
        return True, f"{label} de {amount:.2f} {payment_currency} registrado para la factura {invoice.get('invoice_number')}. Saldo restante: {new_balance:.2f} {invoice_currency}.{discount_note}{credit_note}{verify_note}"

    @staticmethod
    def apply_credit_balance(company_db_name, invoice_id, user_email):
        """Aplica el saldo a favor disponible del cliente (acumulado por
        sobre-pagos previos) a esta factura, hasta cubrir el saldo pendiente."""
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        try:
            invoice = db['invoices'].find_one({"_id": ObjectId(invoice_id)})
        except Exception:
            invoice = None
        if not invoice:
            return False, "Factura no encontrada."
        if invoice.get('payment_method') != 'Crédito' or invoice.get('status') != 'emitida':
            return False, "Esta factura no admite abonos."
        if not invoice.get('client_id'):
            return False, "La factura no tiene cliente asociado."

        client = db['clients'].find_one({"_id": invoice['client_id']})
        credit_usd = float((client or {}).get('credit_balance_usd', 0.0))
        if credit_usd <= 0.01:
            return False, "El cliente no tiene saldo a favor disponible."

        invoice_currency = invoice.get('currency', 'USD')
        total = float(invoice.get('total', 0.0))
        amount_paid = float(invoice.get('amount_paid', 0.0))
        balance_due = round(total - amount_paid, 2)
        if balance_due <= 0.01:
            return False, "Esta factura ya está saldada."

        if invoice_currency == 'USD':
            credit_in_invoice_currency = credit_usd
        else:
            converted, _ = FinancialService.convert(company_db_name, credit_usd, 'USD', invoice_currency)
            if converted is None:
                return False, f"No hay tasa de cambio vigente para aplicar el saldo a favor en {invoice_currency}."
            credit_in_invoice_currency = converted

        apply_amount = round(min(balance_due, credit_in_invoice_currency), 2)
        if invoice_currency == 'USD':
            apply_amount_usd = apply_amount
        else:
            converted, _ = FinancialService.convert(company_db_name, apply_amount, invoice_currency, 'USD')
            apply_amount_usd = round(converted, 2) if converted is not None else round(credit_usd, 2)
        apply_amount_usd = min(apply_amount_usd, round(credit_usd, 2))

        new_amount_paid = round(amount_paid + apply_amount, 2)
        new_balance = round(total - new_amount_paid, 2)
        payment_status = 'pagada' if new_balance <= 0.01 else 'parcial'

        payment_doc = {
            "invoice_id": invoice['_id'],
            "invoice_number": invoice.get('invoice_number'),
            "client_id": invoice.get('client_id'),
            "client_name": invoice.get('client_name'),
            "client_rif": invoice.get('client_rif'),
            "seller": ReceivablesService._resolve_seller(company_db_name, invoice),
            "amount": apply_amount,
            "currency": invoice_currency,
            "amount_usd": apply_amount_usd,
            "amount_ves": None,
            "discount_amount": 0.0,
            "applied_to_invoice": apply_amount,
            "excess_to_credit_usd": 0.0,
            "payment_method": "Saldo a Favor del Cliente",
            "account_id": None,
            "reference": "",
            "reference_verified": None,
            "receipt_image_key": None,
            "notes": "Aplicado desde el saldo a favor acumulado del cliente.",
            "balance_after": new_balance,
            "user": user_email,
            "created_at": datetime.utcnow(),
        }

        try:
            db['ar_payments'].insert_one(payment_doc)
            db['invoices'].update_one(
                {"_id": invoice['_id']},
                {"$set": {
                    "amount_paid": new_amount_paid,
                    "payment_status": payment_status,
                    "updated_at": datetime.utcnow(),
                }}
            )
            db['clients'].update_one(
                {"_id": invoice['client_id']},
                {"$inc": {"credit_balance_usd": -apply_amount_usd}}
            )
            db['client_credit_movements'].insert_one({
                "client_id": invoice['client_id'],
                "client_name": invoice.get('client_name'),
                "type": "applied_to_invoice",
                "amount_usd": -apply_amount_usd,
                "related_invoice_id": invoice['_id'],
                "related_invoice_number": invoice.get('invoice_number'),
                "notes": f"Saldo a favor aplicado a la factura {invoice.get('invoice_number')}",
                "user": user_email,
                "created_at": datetime.utcnow(),
            })
        except Exception as e:
            return False, f"Error al aplicar el saldo a favor: {str(e)}"

        label = "Pago total" if payment_status == 'pagada' else "Abono parcial"
        return True, f"{label} de {apply_amount:.2f} {invoice_currency} aplicado desde el saldo a favor del cliente. Saldo restante: {new_balance:.2f} {invoice_currency}."
