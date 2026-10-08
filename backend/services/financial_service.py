from datetime import datetime
from bson import ObjectId
from database import get_company_db
from services.accounting_categories import normalize_category

SUPPORTED_CURRENCIES = ['USD', 'VES', 'EUR', 'COP']
RATE_CURRENCIES = ['VES', 'EUR', 'COP']


def _convert_amount(amount, from_currency, to_currency, rates):
    """
    Convierte un monto entre monedas usando USD como pivote.
    `rates` es un dict {currency: {"rate": float, ...}} con tasas respecto a USD.
    Retorna (monto_convertido_o_None, tasa_principal_usada_o_None).
    """
    if from_currency == to_currency:
        return amount, None

    if from_currency == 'USD':
        rate_doc = rates.get(to_currency)
        if not rate_doc:
            return None, None
        return amount * rate_doc['rate'], rate_doc['rate']

    if to_currency == 'USD':
        rate_doc = rates.get(from_currency)
        if not rate_doc:
            return None, None
        return amount / rate_doc['rate'], rate_doc['rate']

    usd_amount, rate_used = _convert_amount(amount, from_currency, 'USD', rates)
    if usd_amount is None:
        return None, None
    final_amount, _ = _convert_amount(usd_amount, 'USD', to_currency, rates)
    return final_amount, rate_used


class FinancialService:

    @staticmethod
    def get_company_settings(company_db_name):
        db = get_company_db(company_db_name)
        settings = db['company_settings'].find_one({"_id": "config"})
        if not settings:
            settings = {"_id": "config", "base_currency": "USD"}
        return settings

    @staticmethod
    def update_base_currency(company_db_name, currency):
        currency = (currency or '').strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            return False, "Moneda no soportada."
        db = get_company_db(company_db_name)
        db['company_settings'].update_one(
            {"_id": "config"},
            {"$set": {"base_currency": currency, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        return True, f"Moneda base de la empresa actualizada a {currency}."

    @staticmethod
    def convert(company_db_name, amount, from_currency, to_currency):
        """Wrapper público de conversión de monedas usando las tasas vigentes de la empresa.
        Retorna (monto_convertido_o_None, tasa_usada_o_None)."""
        rates = FinancialService.get_latest_rates(company_db_name)
        return _convert_amount(amount, from_currency, to_currency, rates)

    @staticmethod
    def get_latest_rates(company_db_name):
        db = get_company_db(company_db_name)
        rates = {}
        for currency in RATE_CURRENCIES:
            doc = db['exchange_rates'].find_one({"currency": currency}, sort=[("created_at", -1)])
            if doc:
                doc['_id'] = str(doc['_id'])
            rates[currency] = doc
        return rates

    @staticmethod
    def set_exchange_rate(company_db_name, currency, rate, user_email, source='manual'):
        currency = (currency or '').strip().upper()
        if currency not in RATE_CURRENCIES:
            return False, "Moneda no válida para tasa de cambio."
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            return False, "La tasa debe ser numérica."
        if rate <= 0:
            return False, "La tasa debe ser mayor a cero."

        db = get_company_db(company_db_name)
        db['exchange_rates'].insert_one({
            "currency": currency,
            "rate": rate,
            "source": source,
            "created_by": user_email,
            "created_at": datetime.utcnow()
        })
        return True, f"Tasa de {currency} actualizada a {rate}."

    @staticmethod
    def get_bank_accounts(company_db_name):
        db = get_company_db(company_db_name)
        accounts = list(db['banking_accounts'].find({"is_active": {"$ne": False}}).sort('name', 1))
        for a in accounts:
            a['_id'] = str(a['_id'])
            a.setdefault('balance', 0.0)
        return accounts

    @staticmethod
    def create_bank_account(company_db_name, form_data):
        name = form_data.get('name', '').strip()
        bank_name = form_data.get('bank_name', '').strip()
        currency = form_data.get('currency', 'USD').strip().upper()
        account_type = form_data.get('type', 'bank').strip()
        account_number = form_data.get('account_number', '').strip()

        if not name:
            return False, "El nombre de la cuenta es obligatorio."
        if currency not in SUPPORTED_CURRENCIES:
            return False, "Moneda no soportada."

        try:
            initial_balance = float(form_data.get('initial_balance', 0) or 0)
        except ValueError:
            return False, "El saldo inicial debe ser numérico."

        db = get_company_db(company_db_name)
        db['banking_accounts'].insert_one({
            "name": name,
            "bank_name": bank_name,
            "currency": currency,
            "account_number": account_number,
            "type": account_type,
            "balance": initial_balance,
            "initial_balance": initial_balance,
            "is_active": True,
            "created_at": datetime.utcnow()
        })
        return True, f"Cuenta '{name}' creada con éxito."

    @staticmethod
    def register_transaction(company_db_name, form_data, user_email):
        db = get_company_db(company_db_name)
        account_id = form_data.get('account_id', '').strip()
        tx_type = form_data.get('type', '').strip().upper()

        if tx_type not in ('COBRO', 'PAGO'):
            return False, "Tipo de transacción no válido."

        try:
            amount = float(form_data.get('amount', 0))
        except ValueError:
            return False, "El monto debe ser numérico."
        if amount <= 0:
            return False, "El monto debe ser mayor a cero."

        try:
            account = db['banking_accounts'].find_one({"_id": ObjectId(account_id)})
        except Exception:
            account = None
        if not account:
            return False, "Cuenta bancaria no encontrada."

        account_currency = account.get('currency', 'USD')
        settings = FinancialService.get_company_settings(company_db_name)
        base_currency = settings.get('base_currency', 'USD')
        rates = FinancialService.get_latest_rates(company_db_name)

        amount_base_equivalent, exchange_rate_used = _convert_amount(amount, account_currency, base_currency, rates)

        due_amount_base_raw = form_data.get('due_amount_base', '').strip()
        due_amount_base = None
        exchange_difference = None
        if due_amount_base_raw:
            try:
                due_amount_base = float(due_amount_base_raw)
                if amount_base_equivalent is not None:
                    exchange_difference = amount_base_equivalent - due_amount_base
            except ValueError:
                due_amount_base = None

        current_balance = float(account.get('balance', 0.0))
        new_balance = current_balance + amount if tx_type == 'COBRO' else current_balance - amount
        if tx_type == 'PAGO' and new_balance < 0:
            return False, f"Saldo insuficiente en la cuenta (Disponible: {current_balance})."

        account_category = normalize_category(form_data.get('account_category', ''), tx_type)
        reference = form_data.get('reference', '').strip()

        try:
            db['banking_accounts'].update_one(
                {"_id": account['_id']},
                {"$set": {"balance": new_balance, "updated_at": datetime.utcnow()}}
            )
            db['treasury_transactions'].insert_one({
                "account_id": account['_id'],
                "account_name": account.get('name'),
                "account_category": account_category,
                "type": tx_type,
                "amount": amount,
                "currency": account_currency,
                "base_currency": base_currency,
                "exchange_rate_used": exchange_rate_used,
                "amount_base_equivalent": amount_base_equivalent,
                "due_amount_base": due_amount_base,
                "exchange_difference": exchange_difference,
                "counterparty": form_data.get('counterparty', '').strip(),
                "reference": reference,
                "notes": form_data.get('notes', '').strip(),
                "user": user_email,
                "reconciled": False,
                "reconciled_bank_movement_id": None,
                "created_at": datetime.utcnow()
            })
            return True, f"{tx_type} registrado con éxito. Nuevo saldo de la cuenta: {new_balance:.2f} {account_currency}"
        except Exception as e:
            return False, f"Error al registrar la transacción: {str(e)}"

    @staticmethod
    def get_recent_transactions(company_db_name, limit=25):
        db = get_company_db(company_db_name)
        txs = list(db['treasury_transactions'].find({}).sort('created_at', -1).limit(limit))
        for tx in txs:
            tx['_id'] = str(tx['_id'])
            tx['account_id'] = str(tx['account_id'])
        return txs

    @staticmethod
    def get_account_statement(company_db_name, account_id, filters=None):
        """
        Estado de cuenta real de una cuenta bancaria: Saldo Inicial + cada
        movimiento registrado (cronológico, con saldo corriente) = Saldo
        Final — el "estado de resultados" que faltaba, porque antes el saldo
        inicial se pedía una sola vez al crear la cuenta y nunca más se
        volvía a usar para nada (solo quedaba el campo `balance` mutando sin
        dejar rastro de cómo se llegó ahí).

        Para cuentas creadas ANTES de que `initial_balance` se guardara aparte,
        se reconstruye matemáticamente: saldo_actual - neto_de_movimientos.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            acc_oid = ObjectId(account_id)
        except Exception:
            return None

        account = db['banking_accounts'].find_one({"_id": acc_oid})
        if not account:
            return None

        all_tx = list(db['treasury_transactions'].find({"account_id": acc_oid}).sort('created_at', 1))

        stored_initial = account.get('initial_balance')
        if stored_initial is None:
            net_movement = sum(t['amount'] if t['type'] == 'COBRO' else -t['amount'] for t in all_tx)
            stored_initial = float(account.get('balance', 0.0)) - net_movement

        date_from = (filters or {}).get('date_from', '').strip()
        date_to = (filters or {}).get('date_to', '').strip()
        from_dt, to_dt = None, None
        if date_from:
            try:
                from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                pass
        if date_to:
            try:
                to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            except ValueError:
                pass

        running = stored_initial
        opening_balance = stored_initial
        ledger = []
        for t in all_tx:
            delta = t['amount'] if t['type'] == 'COBRO' else -t['amount']
            if from_dt and t['created_at'] < from_dt:
                running += delta
                opening_balance = running
                continue
            if to_dt and t['created_at'] > to_dt:
                continue
            running += delta
            entry = dict(t)
            entry['running_balance'] = round(running, 2)
            ledger.append(entry)

        for entry in ledger:
            entry['_id'] = str(entry['_id'])
            entry['account_id'] = str(entry['account_id'])

        account['_id'] = str(account['_id'])

        return {
            "account": account,
            "initial_balance": round(stored_initial, 2),
            "opening_balance": round(opening_balance, 2),
            "ledger": ledger,
            "closing_balance": round(running, 2),
            "total_income": round(sum(t['amount'] for t in ledger if t['type'] == 'COBRO'), 2),
            "total_expense": round(sum(t['amount'] for t in ledger if t['type'] == 'PAGO'), 2),
        }

    @staticmethod
    def get_accounts_receivable(company_db_name, client_id=None):
        """
        Cuentas por Cobrar (CxC) agregadas por cliente, a partir del saldo real de
        cada factura a Crédito (campo `amount_paid`, actualizado por
        ReceivablesService.register_payment en cada abono). Retorna una lista de
        {client_id, client_name, client_rif, invoiced_total, collected_total,
        balance_due} ordenada por balance_due descendente. Usada por el Centro de
        Mando, el módulo de Cuentas por Cobrar y el dashboard de la app móvil.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return []

        invoice_query = {"status": "emitida", "payment_method": "Crédito"}
        if client_id:
            try:
                invoice_query["client_id"] = ObjectId(client_id)
            except Exception:
                return []

        invoices = list(db['invoices'].find(invoice_query))
        if not invoices:
            return []

        by_client = {}
        for inv in invoices:
            key = str(inv.get('client_id')) if inv.get('client_id') else f"walkin:{inv.get('client_rif')}"
            entry = by_client.setdefault(key, {
                "client_id": str(inv['client_id']) if inv.get('client_id') else None,
                "client_name": inv.get('client_name'),
                "client_rif": inv.get('client_rif'),
                "invoiced_total": 0.0,
                "collected_total": 0.0,
            })
            entry["invoiced_total"] += float(inv.get('total', 0.0))
            entry["collected_total"] += float(inv.get('amount_paid', 0.0))

        results = []
        for entry in by_client.values():
            entry["balance_due"] = round(entry["invoiced_total"] - entry["collected_total"], 2)
            entry["invoiced_total"] = round(entry["invoiced_total"], 2)
            entry["collected_total"] = round(entry["collected_total"], 2)
            if entry["balance_due"] > 0.01:
                results.append(entry)

        results.sort(key=lambda e: e["balance_due"], reverse=True)
        return results

    @staticmethod
    def _movements_union_pipeline(filters=None):
        """
        Construye el pipeline de agregación que normaliza ventas, compras,
        cobros/pagos de Tesorería y abonos de CxC (sin depósito) a una forma
        común vía $unionWith, para poder filtrar/paginar TODO en el servidor
        de MongoDB en vez de traer colecciones completas a memoria de Python.
        """
        invoices_project = {"$project": {
            "type": {"$literal": "venta"},
            "label": {"$cond": [{"$eq": ["$doc_type", "nota_entrega"]}, "Nota de Entrega", "Factura"]},
            "reference": "$invoice_number",
            "counterparty": "$client_name",
            "amount": {"$ifNull": ["$total", 0.0]},
            "currency": {"$ifNull": ["$currency", "USD"]},
            "user": {"$ifNull": ["$seller", "$user"]},
            "created_at": "$created_at",
            "voided": {"$eq": ["$status", "anulada"]},
            "_id": 0,
        }}
        purchases_project = {"$project": {
            "type": {"$literal": "compra"},
            "label": {"$literal": "Compra"},
            "reference": "$supplier_name",
            "counterparty": "$supplier_name",
            "amount": {"$ifNull": ["$total_cost", 0.0]},
            "currency": {"$literal": "USD"},
            "user": "$user",
            "created_at": "$timestamp",
            "voided": {"$literal": False},
            "_id": 0,
        }}
        treasury_project = {"$project": {
            "type": {"$cond": [{"$eq": ["$type", "COBRO"]}, "cobro", "pago"]},
            "label": {"$cond": [{"$eq": ["$type", "COBRO"]}, "Cobro", "Pago"]},
            "reference": {"$ifNull": ["$reference", "$account_name"]},
            "counterparty": "$counterparty",
            "amount": {"$ifNull": ["$amount", 0.0]},
            "currency": {"$ifNull": ["$currency", "USD"]},
            "user": "$user",
            "created_at": "$created_at",
            "voided": {"$literal": False},
            "_id": 0,
        }}
        ar_payments_project = {"$project": {
            "type": {"$literal": "abono"},
            "label": {"$literal": "Abono CxC (pendiente de depósito)"},
            "reference": "$invoice_number",
            "counterparty": "$client_name",
            "amount": {"$ifNull": ["$amount", 0.0]},
            "currency": {"$ifNull": ["$currency", "USD"]},
            "user": "$user",
            "created_at": "$created_at",
            "voided": {"$literal": False},
            "_id": 0,
        }}

        pipeline = [
            invoices_project,
            {"$unionWith": {"coll": "purchase_orders", "pipeline": [purchases_project]}},
            {"$unionWith": {"coll": "treasury_transactions", "pipeline": [treasury_project]}},
            {"$unionWith": {"coll": "ar_payments", "pipeline": [
                {"$match": {"account_id": None}},
                ar_payments_project,
            ]}},
        ]

        match_stage = {}
        if filters:
            mtype = (filters.get('type') or '').strip()
            if mtype:
                match_stage['type'] = mtype

            responsible = (filters.get('responsible') or '').strip()
            if responsible:
                match_stage['user'] = responsible

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
                    match_stage['created_at'] = date_query

        if match_stage:
            pipeline.append({"$match": match_stage})

        return pipeline

    @staticmethod
    def get_movements_feed(company_db_name, filters=None, page=1, per_page=25):
        """
        Bitácora auditable de movimientos de la empresa: ventas, compras, cobros,
        pagos y abonos de CxC, unificados y paginados a nivel de base de datos
        (agregación $unionWith) para no cargar las colecciones completas en
        memoria conforme la bitácora va creciendo. Soporta filtro por tipo,
        responsable y rango de fechas.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        pipeline = FinancialService._movements_union_pipeline(filters)

        count_result = list(db['invoices'].aggregate(pipeline + [{"$count": "total"}]))
        total_count = count_result[0]['total'] if count_result else 0

        skip = (page - 1) * per_page
        data_pipeline = pipeline + [
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": per_page},
        ]
        items = list(db['invoices'].aggregate(data_pipeline))
        return items, total_count

    @staticmethod
    def get_responsibles(company_db_name):
        """Lista de usuarios (email+nombre) para el filtro 'Responsable' de la bitácora."""
        db = get_company_db(company_db_name)
        if db is None:
            return []
        users = list(db['users'].find({}, {"name": 1, "email": 1}))
        for u in users:
            u['_id'] = str(u['_id'])
        return users

    @staticmethod
    def get_reconciliation_summary(company_db_name):
        db = get_company_db(company_db_name)
        cursor = db['treasury_transactions'].find({})
        total_cobros = 0.0
        total_pagos = 0.0
        total_exchange_difference = 0.0
        count = 0
        for tx in cursor:
            count += 1
            amt = float(tx.get('amount_base_equivalent') or tx.get('amount', 0.0))
            if tx.get('type') == 'COBRO':
                total_cobros += amt
            else:
                total_pagos += amt
            if tx.get('exchange_difference') is not None:
                total_exchange_difference += float(tx['exchange_difference'])

        return {
            "count": count,
            "total_cobros_base": total_cobros,
            "total_pagos_base": total_pagos,
            "net_flow_base": total_cobros - total_pagos,
            "total_exchange_difference": total_exchange_difference,
        }
