from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.financial_service import FinancialService

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
        if filters:
            client_id = (filters.get('client_id') or '').strip()
            if client_id:
                try:
                    query['client_id'] = ObjectId(client_id)
                except Exception:
                    return []

            seller = (filters.get('seller') or '').strip()
            if seller:
                query['seller'] = seller

            search = (filters.get('search') or '').strip()
            if search:
                query['$or'] = [
                    {"invoice_number": {"$regex": search, "$options": "i"}},
                    {"client_name": {"$regex": search, "$options": "i"}},
                    {"client_rif": {"$regex": search, "$options": "i"}},
                ]

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
        return results

    @staticmethod
    def get_aging_summary(company_db_name):
        items = ReceivablesService.get_invoice_receivables(company_db_name)
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
    def register_payment(company_db_name, form_data, user_email):
        """
        Registra un abono (parcial o total) sobre una factura a Crédito.
        Dos efectos SIEMPRE atómicos para que la deuda y el libro de abonos
        nunca queden desincronizados:
          1. Inserta un registro inmutable en ar_payments (auditoría: factura,
             cliente, vendedor, monto, método, fecha, usuario que lo registró).
          2. Actualiza amount_paid/payment_status en la factura para que el
             saldo pendiente baje de inmediato en todos los reportes.
        Si se indica una cuenta bancaria/caja, además refleja el cobro en
        Tesorería para que la conciliación bancaria también lo vea.
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

        total = float(invoice.get('total', 0.0))
        amount_paid = float(invoice.get('amount_paid', 0.0))
        balance_due = round(total - amount_paid, 2)
        if balance_due <= 0.01:
            return False, "Esta factura ya está saldada."
        if amount > balance_due + 0.01:
            return False, f"El abono (${amount:.2f}) supera el saldo pendiente (${balance_due:.2f})."

        new_amount_paid = round(amount_paid + amount, 2)
        new_balance = round(total - new_amount_paid, 2)
        payment_status = 'pagada' if new_balance <= 0.01 else 'parcial'

        payment_method = (form_data.get('payment_method') or 'Efectivo').strip() or 'Efectivo'
        account_id = (form_data.get('account_id') or '').strip()
        reference = (form_data.get('reference') or '').strip()
        notes = (form_data.get('notes') or '').strip()

        payment_doc = {
            "invoice_id": invoice['_id'],
            "invoice_number": invoice.get('invoice_number'),
            "client_id": invoice.get('client_id'),
            "client_name": invoice.get('client_name'),
            "client_rif": invoice.get('client_rif'),
            "seller": invoice.get('seller'),
            "amount": amount,
            "currency": invoice.get('currency', 'USD'),
            "payment_method": payment_method,
            "account_id": ObjectId(account_id) if account_id else None,
            "reference": reference,
            "notes": notes,
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
        except Exception as e:
            return False, f"Error al registrar el abono: {str(e)}"

        if account_id:
            FinancialService.register_transaction(company_db_name, {
                "account_id": account_id,
                "type": "COBRO",
                "amount": str(amount),
                "counterparty": invoice.get('client_name'),
                "reference": invoice.get('invoice_number'),
                "notes": f"Abono a factura {invoice.get('invoice_number')}" + (f" — {notes}" if notes else ""),
            }, user_email)

        label = "Pago total" if payment_status == 'pagada' else "Abono parcial"
        return True, f"{label} de ${amount:.2f} registrado para la factura {invoice.get('invoice_number')}. Saldo restante: ${new_balance:.2f}."
