from datetime import datetime
from bson import ObjectId
from database import get_company_db

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

        try:
            db['banking_accounts'].update_one(
                {"_id": account['_id']},
                {"$set": {"balance": new_balance, "updated_at": datetime.utcnow()}}
            )
            db['treasury_transactions'].insert_one({
                "account_id": account['_id'],
                "account_name": account.get('name'),
                "type": tx_type,
                "amount": amount,
                "currency": account_currency,
                "base_currency": base_currency,
                "exchange_rate_used": exchange_rate_used,
                "amount_base_equivalent": amount_base_equivalent,
                "due_amount_base": due_amount_base,
                "exchange_difference": exchange_difference,
                "counterparty": form_data.get('counterparty', '').strip(),
                "reference": form_data.get('reference', '').strip(),
                "notes": form_data.get('notes', '').strip(),
                "user": user_email,
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
