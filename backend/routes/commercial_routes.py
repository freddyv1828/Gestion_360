from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, jsonify
from services.commercial_service import CommercialService
from services.dropi_service import DropiService
from services.financial_service import FinancialService
from services.invoicing_service import InvoicingService
from services.client_service import ClientService
from services.exchange_rate_service import ExchangeRateService
from services.order_service import OrderService
from services.coupon_service import CouponService
from services.receivables_service import ReceivablesService
from services.route_service import RouteService
from services.commission_service import CommissionService
from services.reconciliation_service import ReconciliationService
from services.accounting_categories import INCOME_CATEGORIES, EXPENSE_CATEGORIES
from services.pdf_service import generate_invoice_pdf, generate_dispatch_guide_pdf, generate_table_pdf, generate_commission_receipt_pdf
from services.export_service import rows_to_csv
from database import get_company_db
from rbac import is_warehouse_only_role
from utils import json_safe

commercial_bp = Blueprint('commercial', __name__, template_folder='../../templates/commercial')

def get_active_company_db():
    """Retorna la base de datos de la empresa desde la sesión activa de forma segura."""
    return session.get('company_db')

def _get_filter_options(company_db_name):
    """Opciones compartidas por las bandejas de Pedidos, Cobros y Pagos para
    filtrar por vendedor, ruta y cliente. 'Vendedor' se restringe a usuarios
    con ruta asignada (dueños de ruta), no a todos los usuarios del sistema
    (antes el dropdown de Cobros listaba hasta el administrador y el
    almacenista)."""
    db = get_company_db(company_db_name)
    if db is None:
        return [], [], []
    sellers = list(db['users'].find({"route_number": {"$ne": None}}, {"name": 1, "email": 1, "route_number": 1}).sort('route_number', 1))
    for s in sellers:
        s['_id'] = str(s['_id'])
    routes = RouteService.list_routes(company_db_name)
    clients = list(db['clients'].find({"is_active": {"$ne": False}}, {"name": 1, "route_number": 1}).sort('name', 1))
    for c in clients:
        c['_id'] = str(c['_id'])
    return sellers, routes, clients

@commercial_bp.route('/')
def index():
    return redirect(url_for('commercial.financial'))

@commercial_bp.route('/financial')
def financial():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    settings = FinancialService.get_company_settings(company_db_name)
    base_currency = settings.get('base_currency', 'USD')
    rates = FinancialService.get_latest_rates(company_db_name)
    accounts = FinancialService.get_bank_accounts(company_db_name)
    summary = FinancialService.get_reconciliation_summary(company_db_name)
    aging = ReceivablesService.get_aging_summary(company_db_name)
    sales_summary = InvoicingService.get_sales_summary(company_db_name)

    page = request.args.get('page', 1, type=int)
    per_page = 25
    filters = {
        'type': request.args.get('type', ''),
        'responsible': request.args.get('responsible', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    feed, total_count = FinancialService.get_movements_feed(company_db_name, filters=filters, page=page, per_page=per_page)
    responsibles = FinancialService.get_responsibles(company_db_name)

    total_accounts_base = 0.0
    for acc in accounts:
        converted, _ = FinancialService.convert(company_db_name, acc.get('balance', 0.0), acc.get('currency', 'USD'), base_currency)
        total_accounts_base += converted if converted is not None else 0.0

    db = get_company_db(company_db_name)
    purchases_total = 0.0
    if db is not None:
        agg = list(db['purchase_orders'].aggregate([{"$group": {"_id": None, "total": {"$sum": "$total_cost"}}}]))
        purchases_total = agg[0]['total'] if agg else 0.0

    return render_template(
        'commercial/financial.html',
        settings=settings,
        rates=rates,
        summary=summary,
        aging=aging,
        sales_summary=sales_summary,
        purchases_total=purchases_total,
        total_accounts_base=total_accounts_base,
        feed=feed,
        filters=filters,
        responsibles=responsibles,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/financial/export')
def export_financial():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'type': request.args.get('type', ''),
        'responsible': request.args.get('responsible', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    feed, _ = FinancialService.get_movements_feed(company_db_name, filters=filters, page=1, per_page=100000)
    for m in feed:
        m['created_at_str'] = m['created_at'].strftime('%Y-%m-%d %H:%M') if m.get('created_at') else ''
        m['voided_label'] = 'Sí' if m.get('voided') else 'No'

    if export_format == 'pdf':
        headers = ['Fecha', 'Tipo', 'Referencia', 'Contraparte', 'Monto', 'Moneda', 'Responsable']
        rows = [[
            m.get('created_at_str', ''), m.get('label', ''), m.get('reference', '') or '', m.get('counterparty', '') or '',
            f"{m.get('amount', 0):.2f}", m.get('currency', ''), m.get('user', '') or '',
        ] for m in feed]
        pdf_bytes = generate_table_pdf("Bitácora de Movimientos Financieros", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="bitacora_movimientos.pdf"'})

    headers_map = {
        'created_at_str': 'Fecha', 'label': 'Tipo', 'reference': 'Referencia', 'counterparty': 'Contraparte',
        'amount': 'Monto', 'currency': 'Moneda', 'user': 'Responsable', 'voided_label': 'Anulada',
    }
    csv_bytes = rows_to_csv(feed, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="bitacora_movimientos.csv"'})

@commercial_bp.route('/financial/currency/save', methods=['POST'])
def save_base_currency():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = FinancialService.update_base_currency(company_db_name, request.form.get('base_currency'))
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury'))

@commercial_bp.route('/financial/rates/save', methods=['POST'])
def save_exchange_rate():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = FinancialService.set_exchange_rate(
        company_db_name,
        request.form.get('currency'),
        request.form.get('rate'),
        user_email
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury'))

@commercial_bp.route('/financial/rates/sync-bcv', methods=['POST'])
def sync_bcv_rates():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = ExchangeRateService.sync_bcv_rates(company_db_name, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury'))

@commercial_bp.route('/financial/accounts/save', methods=['POST'])
def save_bank_account():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = FinancialService.create_bank_account(company_db_name, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury'))

@commercial_bp.route('/financial/transaction/save', methods=['POST'])
def save_treasury_transaction():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = FinancialService.register_transaction(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury'))

@commercial_bp.route('/treasury')
def treasury():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    settings = FinancialService.get_company_settings(company_db_name)
    rates = FinancialService.get_latest_rates(company_db_name)
    accounts = FinancialService.get_bank_accounts(company_db_name)
    transactions = FinancialService.get_recent_transactions(company_db_name)
    summary = FinancialService.get_reconciliation_summary(company_db_name)

    return render_template(
        'commercial/treasury.html',
        settings=settings,
        rates=rates,
        accounts=accounts,
        transactions=transactions,
        summary=summary,
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
    )

@commercial_bp.route('/treasury/statement/<account_id>')
def treasury_statement(account_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    filters = {
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    statement = FinancialService.get_account_statement(company_db_name, account_id, filters=filters)
    if statement is None:
        flash("Cuenta bancaria no encontrada.", "danger")
        return redirect(url_for('commercial.treasury'))

    return render_template('commercial/treasury_statement.html', filters=filters, **statement)

@commercial_bp.route('/treasury/statement/<account_id>/export')
def export_account_statement(account_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    statement = FinancialService.get_account_statement(company_db_name, account_id, filters=filters)
    if statement is None:
        flash("Cuenta bancaria no encontrada.", "danger")
        return redirect(url_for('commercial.treasury'))

    rows = []
    rows.append({'fecha': '', 'tipo': '', 'referencia': '', 'descripcion': 'SALDO INICIAL', 'ingreso': '', 'egreso': '', 'saldo': f"{statement['opening_balance']:.2f}"})
    for t in statement['ledger']:
        rows.append({
            'fecha': t['created_at'].strftime('%Y-%m-%d') if t.get('created_at') else '',
            'tipo': t.get('type', ''),
            'referencia': t.get('reference', ''),
            'descripcion': t.get('counterparty', '') or t.get('account_category', ''),
            'ingreso': f"{t['amount']:.2f}" if t.get('type') == 'COBRO' else '',
            'egreso': f"{t['amount']:.2f}" if t.get('type') == 'PAGO' else '',
            'saldo': f"{t.get('running_balance', 0):.2f}",
        })

    if export_format == 'pdf':
        headers = ['Fecha', 'Tipo', 'Referencia', 'Descripción', 'Ingreso', 'Egreso', 'Saldo']
        pdf_rows = [[r['fecha'], r['tipo'], r['referencia'], r['descripcion'], r['ingreso'], r['egreso'], r['saldo']] for r in rows]
        pdf_bytes = generate_table_pdf(f"Estado de Cuenta — {statement['account']['name']}", session.get('company_name', 'Gestión 360'), headers, pdf_rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': f'attachment; filename="estado_cuenta_{statement["account"]["name"]}.pdf"'})

    headers_map = {'fecha': 'Fecha', 'tipo': 'Tipo', 'referencia': 'Referencia', 'descripcion': 'Descripción', 'ingreso': 'Ingreso', 'egreso': 'Egreso', 'saldo': 'Saldo'}
    csv_bytes = rows_to_csv(rows, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': f'attachment; filename="estado_cuenta_{statement["account"]["name"]}.csv"'})

@commercial_bp.route('/treasury/reconciliation/<account_id>')
def treasury_reconciliation(account_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    filters = {
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    view = ReconciliationService.get_reconciliation_view(company_db_name, account_id, filters=filters)
    if view is None:
        flash("Cuenta bancaria no encontrada.", "danger")
        return redirect(url_for('commercial.treasury'))

    return render_template('commercial/treasury_reconciliation.html', filters=filters, **view)

@commercial_bp.route('/treasury/reconciliation/<account_id>/export')
def export_reconciliation(account_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    view = ReconciliationService.get_reconciliation_view(company_db_name, account_id, filters=filters)
    if view is None:
        flash("Cuenta bancaria no encontrada.", "danger")
        return redirect(url_for('commercial.treasury'))

    rows = []
    for b in view['matched']:
        rows.append({'fecha': b['date'].strftime('%Y-%m-%d') if b.get('date') else '', 'estado': 'Conciliado', 'tipo': b.get('bank_type', ''),
                     'referencia': b.get('reference', ''), 'descripcion': b.get('description', ''), 'monto': f"{b.get('amount', 0):.2f}"})
    for b in view['bank_only']:
        rows.append({'fecha': b['date'].strftime('%Y-%m-%d') if b.get('date') else '', 'estado': 'Solo en Banco', 'tipo': b.get('bank_type', ''),
                     'referencia': b.get('reference', ''), 'descripcion': b.get('description', ''), 'monto': f"{b.get('amount', 0):.2f}"})
    for t in view['system_only']:
        rows.append({'fecha': t['created_at'].strftime('%Y-%m-%d') if t.get('created_at') else '', 'estado': 'Solo en Sistema',
                     'tipo': t.get('type', ''), 'referencia': t.get('reference', ''),
                     'descripcion': t.get('counterparty', '') or t.get('account_category', ''), 'monto': f"{t.get('amount', 0):.2f}"})

    if export_format == 'pdf':
        headers = ['Fecha', 'Estado', 'Tipo', 'Referencia', 'Descripción', 'Monto']
        pdf_rows = [[r['fecha'], r['estado'], r['tipo'], r['referencia'], r['descripcion'], r['monto']] for r in rows]
        pdf_bytes = generate_table_pdf(f"Conciliación Bancaria — {view['account']['name']}", session.get('company_name', 'Gestión 360'), headers, pdf_rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': f'attachment; filename="conciliacion_{view["account"]["name"]}.pdf"'})

    headers_map = {'fecha': 'Fecha', 'estado': 'Estado', 'tipo': 'Tipo', 'referencia': 'Referencia', 'descripcion': 'Descripción', 'monto': 'Monto'}
    csv_bytes = rows_to_csv(rows, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': f'attachment; filename="conciliacion_{view["account"]["name"]}.csv"'})

@commercial_bp.route('/treasury/reconciliation/<account_id>/import', methods=['POST'])
def import_bank_statement(account_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    uploaded_file = request.files.get('statement_file')
    if not uploaded_file or not uploaded_file.filename:
        flash("Selecciona un archivo .xlsx del estado de cuenta.", "danger")
        return redirect(url_for('commercial.treasury_reconciliation', account_id=account_id))

    file_bytes = uploaded_file.read()
    success, message, _ = ReconciliationService.import_bank_statement(
        company_db_name, account_id, file_bytes, uploaded_file.filename, user_email
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury_reconciliation', account_id=account_id))

@commercial_bp.route('/treasury/reconciliation/<account_id>/clear', methods=['POST'])
def clear_bank_statement(account_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = ReconciliationService.clear_bank_statement(company_db_name, account_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.treasury_reconciliation', account_id=account_id))

@commercial_bp.route('/treasury/export')
def export_treasury():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    transactions = FinancialService.get_recent_transactions(company_db_name, limit=100000)
    for tx in transactions:
        tx['created_at_str'] = tx.get('created_at').strftime('%Y-%m-%d %H:%M') if tx.get('created_at') else ''
        tx['reconciled_label'] = 'Conciliado' if tx.get('reconciled') else 'Pendiente'

    if export_format == 'pdf':
        headers = ['Fecha', 'Tipo', 'Cuenta', 'Cuenta Contable', 'Monto', 'Moneda', 'Equiv. Base', 'Dif. Cambiaria', 'Beneficiario', 'N° Operación', 'Conciliado']
        rows = [[
            tx.get('created_at_str', ''), tx.get('type', ''), tx.get('account_name', ''), tx.get('account_category', ''),
            f"{tx.get('amount', 0):.2f}", tx.get('currency', ''), f"{tx.get('amount_base_equivalent', 0) or 0:.2f}",
            f"{tx.get('exchange_difference', 0) or 0:.2f}", tx.get('counterparty', ''), tx.get('reference', ''), tx.get('reconciled_label', ''),
        ] for tx in transactions]
        pdf_bytes = generate_table_pdf("Movimientos de Tesorería", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="tesoreria.pdf"'})

    headers_map = {
        'created_at_str': 'Fecha', 'type': 'Tipo', 'account_name': 'Cuenta', 'account_category': 'Cuenta Contable',
        'amount': 'Monto', 'currency': 'Moneda', 'amount_base_equivalent': 'Equiv. Base', 'exchange_difference': 'Dif. Cambiaria',
        'counterparty': 'Beneficiario', 'reference': 'N° Operación', 'notes': 'Notas', 'reconciled_label': 'Conciliado',
    }
    csv_bytes = rows_to_csv(transactions, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="tesoreria.csv"'})

@commercial_bp.route('/receivables')
def receivables():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    filters = {
        'search': request.args.get('search', ''),
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'client_id': request.args.get('client_id', ''),
        'bucket': request.args.get('bucket', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    items = ReceivablesService.get_invoice_receivables(company_db_name, filters=filters)
    aging = ReceivablesService.get_aging_summary(company_db_name)
    accounts = FinancialService.get_bank_accounts(company_db_name)
    sellers, routes, clients = _get_filter_options(company_db_name)

    return render_template(
        'commercial/receivables.html',
        items=items,
        aging=aging,
        accounts=accounts,
        sellers=sellers,
        routes=routes,
        clients=clients,
        filters=filters,
    )

@commercial_bp.route('/receivables/payment/save', methods=['POST'])
def save_receivable_payment():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    receipt_file = request.files.get('receipt_image')
    success, message = ReceivablesService.register_payment(company_db_name, request.form, user_email, receipt_file=receipt_file)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.receivables'))

@commercial_bp.route('/receivables/payment/apply-credit', methods=['POST'])
def apply_receivable_credit():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    invoice_id = request.form.get('invoice_id', '')
    success, message = ReceivablesService.apply_credit_balance(company_db_name, invoice_id, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.receivables'))

@commercial_bp.route('/receivables/invoice/<invoice_id>/payments.json')
def receivable_invoice_payments_json(invoice_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return jsonify({"error": "No autorizado"}), 401
    payments = ReceivablesService.get_payments_for_invoice(company_db_name, invoice_id)
    return jsonify({"payments": json_safe(payments)})

@commercial_bp.route('/receivables/invoice/<invoice_id>/payments/export')
def export_invoice_payments(invoice_id):
    """Descarga individual del historial de abonos de UNA factura — auditoría
    puntual para cobranza (quién pagó qué, cuándo y cómo, sin tener que
    exportar toda la cartera)."""
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    invoice = InvoicingService.get_invoice(company_db_name, invoice_id)
    invoice_number = invoice.get('invoice_number') if invoice else invoice_id
    payments = ReceivablesService.get_payments_for_invoice(company_db_name, invoice_id)
    for p in payments:
        p['created_at_str'] = p['created_at'].strftime('%Y-%m-%d %H:%M') if p.get('created_at') else ''

    if export_format == 'pdf':
        headers = ['Fecha', 'Monto', 'Moneda', 'Método', 'Referencia', 'Usuario', 'Saldo Después', 'Notas']
        rows = [[
            p.get('created_at_str', ''), f"{p.get('amount', 0):.2f}", p.get('currency', ''), p.get('payment_method', ''),
            p.get('reference', '') or '—', p.get('user', '') or '—',
            f"{p.get('balance_after', 0):.2f}" if p.get('balance_after') is not None else '—', p.get('notes', '') or '—',
        ] for p in payments]
        pdf_bytes = generate_table_pdf(f"Historial de Abonos — Factura {invoice_number}", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': f'attachment; filename="abonos_{invoice_number}.pdf"'})

    headers_map = {
        'created_at_str': 'Fecha', 'amount': 'Monto', 'currency': 'Moneda', 'payment_method': 'Método',
        'reference': 'Referencia', 'user': 'Usuario', 'balance_after': 'Saldo Después', 'notes': 'Notas',
    }
    csv_bytes = rows_to_csv(payments, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': f'attachment; filename="abonos_{invoice_number}.csv"'})

@commercial_bp.route('/receivables/client/<client_id>/statement.json')
def receivable_client_statement_json(client_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return jsonify({"error": "No autorizado"}), 401
    statement = ReceivablesService.get_client_statement(company_db_name, client_id)
    return jsonify(json_safe(statement))

@commercial_bp.route('/receivables/export')
def export_receivables():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'search': request.args.get('search', ''),
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'client_id': request.args.get('client_id', ''),
        'bucket': request.args.get('bucket', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    items = ReceivablesService.get_invoice_receivables(company_db_name, filters=filters)
    for r in items:
        r['created_at_str'] = r['created_at'].strftime('%Y-%m-%d') if r.get('created_at') else ''
        r['seller_label'] = r.get('seller') or 'S/A'

    if export_format == 'pdf':
        headers = ['Factura', 'Cliente', 'RIF', 'Vendedor', 'Fecha', 'Días', 'Tramo', 'Facturado', 'Abonado', 'Saldo']
        rows = [[
            r.get('invoice_number', ''), r.get('client_name', ''), r.get('client_rif', ''), r.get('seller_label', ''),
            r.get('created_at_str', ''), str(r.get('days_outstanding', 0)), r.get('aging_bucket', ''),
            f"${r.get('total', 0):.2f}", f"${r.get('amount_paid', 0):.2f}", f"${r.get('balance_due', 0):.2f}",
        ] for r in items]
        pdf_bytes = generate_table_pdf("Cuentas por Cobrar — Detalle y Antigüedad de Saldos", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="cuentas_por_cobrar_detalle.pdf"'})

    headers_map = {
        'invoice_number': 'Factura', 'client_name': 'Cliente', 'client_rif': 'RIF', 'seller_label': 'Vendedor',
        'created_at_str': 'Fecha', 'days_outstanding': 'Días', 'aging_bucket': 'Tramo',
        'total': 'Facturado', 'amount_paid': 'Abonado', 'balance_due': 'Saldo',
    }
    csv_bytes = rows_to_csv(items, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="cuentas_por_cobrar_detalle.csv"'})

@commercial_bp.route('/receivables/inbox')
def payment_inbox():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    filters = {
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'client_id': request.args.get('client_id', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    inbox = ReceivablesService.get_payment_inbox(company_db_name, filters=filters)
    sellers, routes, clients = _get_filter_options(company_db_name)

    return render_template('commercial/payment_inbox.html', inbox=inbox, filters=filters, sellers=sellers, routes=routes, clients=clients)

@commercial_bp.route('/receivables/payment/<payment_id>/verify', methods=['POST'])
def verify_receivable_payment(payment_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = ReceivablesService.manually_verify_payment(company_db_name, payment_id, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.payment_inbox'))

@commercial_bp.route('/products')
def products():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    if is_warehouse_only_role(session.get('user_role')):
        flash("Tu rol (Almacenista) no tiene acceso al Catálogo administrativo (costos/márgenes). Usa el módulo de Almacén.", "warning")
        return redirect(url_for('warehouse_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15

    filters = {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'brand': request.args.get('brand', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'stock_filter': request.args.get('stock_filter', ''),
    }

    products_list, total_count = CommercialService.get_paginated_products(
        company_db_name, filters=filters, page=page, per_page=per_page
    )

    warehouses = CommercialService.get_warehouses(company_db_name)
    categories, brands = CommercialService.get_distinct_categories_and_brands(company_db_name)
    alert_counts = CommercialService.get_stock_alert_counts(company_db_name, filters.get('warehouse_id'))

    return render_template(
        'commercial/products.html',
        products=products_list,
        warehouses=warehouses,
        categories=categories,
        brands=brands,
        filters=filters,
        alert_counts=alert_counts,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/products/save', methods=['POST'])
def save_product():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    creator_email = session.get('user_email', 'admin@gestion360.com')
    rif = session.get('company_rif', 'J-12345678-9')
    image_file = request.files.get('image_file')

    success, message = CommercialService.create_commercial_product(
        company_db_name, request.form, creator_email, image_file=image_file, rif=rif
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.products'))

@commercial_bp.route('/warehouses/save', methods=['POST'])
def save_warehouse():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = CommercialService.create_warehouse(company_db_name, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.products'))

@commercial_bp.route('/products/movement', methods=['POST'])
def register_movement():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = CommercialService.register_movement(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.products'))

@commercial_bp.route('/products/delete/<product_id>', methods=['POST'])
def delete_product(product_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = CommercialService.soft_delete_product(company_db_name, product_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.products'))

@commercial_bp.route('/clients')
def clients():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15
    filters = {
        'search': request.args.get('search', ''),
        'client_type': request.args.get('client_type', ''),
        'credit_min': request.args.get('credit_min', ''),
        'credit_max': request.args.get('credit_max', ''),
        'route_number': request.args.get('route_number', ''),
    }

    clients_list, total_count = ClientService.get_paginated_clients(
        company_db_name, filters=filters, page=page, per_page=per_page
    )

    sellers, routes, _ = _get_filter_options(company_db_name)

    return render_template(
        'commercial/clients.html',
        clients=clients_list,
        filters=filters,
        sellers=sellers,
        routes=routes,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/clients/export')
def export_clients():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'search': request.args.get('search', ''),
        'client_type': request.args.get('client_type', ''),
        'credit_min': request.args.get('credit_min', ''),
        'credit_max': request.args.get('credit_max', ''),
        'route_number': request.args.get('route_number', ''),
    }
    clients_list, _ = ClientService.get_paginated_clients(company_db_name, filters=filters, page=1, per_page=100000)
    for c in clients_list:
        c['route_label'] = f"Ruta {c['route_number']}" if c.get('route_number') is not None else 'Sin asignar'
        c['seller_label'] = c.get('seller_name') or 'Sin asignar'

    if export_format == 'pdf':
        headers = ['Nombre', 'RIF/Cédula', 'Tipo', 'Email', 'Teléfono', 'Límite de Crédito', 'Ruta', 'Vendedor']
        rows = [[
            c.get('name', ''), c.get('rif_cedula', ''), 'Fiscal' if c.get('client_type') == 'fiscal' else 'Natural',
            c.get('email', ''), c.get('phone', ''), f"${c.get('credit_limit', 0):.2f}",
            c.get('route_label', ''), c.get('seller_label', ''),
        ] for c in clients_list]
        pdf_bytes = generate_table_pdf("Directorio de Clientes", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="clientes.pdf"'})

    headers_map = {
        'name': 'Nombre', 'rif_cedula': 'RIF/Cédula', 'client_type': 'Tipo',
        'email': 'Email', 'phone': 'Teléfono', 'address': 'Dirección', 'credit_limit': 'Límite de Crédito',
        'route_label': 'Ruta', 'seller_label': 'Vendedor',
    }
    csv_bytes = rows_to_csv(clients_list, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="clientes.csv"'})

@commercial_bp.route('/clients/save', methods=['POST'])
def save_client():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    creator_email = session.get('user_email', 'admin@gestion360.com')
    success, message = ClientService.create_or_update_client(company_db_name, request.form, creator_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.clients'))

@commercial_bp.route('/clients/<client_id>/reassign-route', methods=['POST'])
def reassign_client_route(client_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    actor_email = session.get('user_email', 'admin@gestion360.com')
    success, message = ClientService.reassign_route(
        company_db_name, client_id, request.form.get('route_number', ''), actor_email
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.clients'))

@commercial_bp.route('/clients/delete/<client_id>', methods=['POST'])
def delete_client(client_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = ClientService.soft_delete_client(company_db_name, client_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.clients'))

@commercial_bp.route('/orders')
def orders():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15
    status = request.args.get('status', 'all')
    filters = {
        'search': request.args.get('search', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'client_id': request.args.get('client_id', ''),
    }

    orders_list, total_count = OrderService.get_paginated_orders(company_db_name, status=status, filters=filters, page=page, per_page=per_page)
    status_counts = OrderService.get_status_counts(company_db_name)
    warehouses = CommercialService.get_warehouses(company_db_name)
    sellers, routes, clients = _get_filter_options(company_db_name)

    return render_template(
        'commercial/orders.html',
        orders=orders_list,
        status=status,
        filters=filters,
        status_counts=status_counts,
        warehouses=warehouses,
        sellers=sellers,
        routes=routes,
        clients=clients,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/orders/export')
def export_orders():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    status = request.args.get('status', 'all')
    filters = {
        'search': request.args.get('search', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'client_id': request.args.get('client_id', ''),
    }
    orders_list, _ = OrderService.get_paginated_orders(company_db_name, status=status, filters=filters, page=1, per_page=100000)

    for o in orders_list:
        o['created_at_str'] = o.get('created_at', '')[:16].replace('T', ' ') if o.get('created_at') else ''
        o['doc_type_label'] = 'Nota de Entrega' if o.get('doc_type') == 'nota_entrega' else 'Factura Fiscal'
        o['item_count'] = len(o.get('items', []))

    if export_format == 'pdf':
        headers = ['N° Pedido', 'Fecha', 'Cliente', 'RIF', 'Documento', 'Estado', 'Líneas', 'Comentario']
        rows = [[
            o.get('order_number', ''), o.get('created_at_str', ''), o.get('client_name', ''), o.get('client_rif', ''),
            o.get('doc_type_label', ''), o.get('status', '').upper(), str(o.get('item_count', 0)), o.get('comment', ''),
        ] for o in orders_list]
        pdf_bytes = generate_table_pdf("Pedidos", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="pedidos.pdf"'})

    headers_map = {
        'order_number': 'N° Pedido', 'created_at_str': 'Fecha', 'client_name': 'Cliente', 'client_rif': 'RIF',
        'doc_type_label': 'Documento', 'status': 'Estado', 'item_count': 'Líneas', 'comment': 'Comentario',
    }
    csv_bytes = rows_to_csv(orders_list, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="pedidos.csv"'})

@commercial_bp.route('/orders/save', methods=['POST'])
def save_order():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message, order_id = OrderService.create_order(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    if success and order_id:
        return redirect(url_for('commercial.order_detail', order_id=order_id))
    return redirect(url_for('commercial.orders'))

@commercial_bp.route('/orders/<order_id>')
def order_detail(order_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    order = OrderService.get_order(company_db_name, order_id)
    if not order:
        flash("Pedido no encontrado.", "danger")
        return redirect(url_for('commercial.orders'))

    warehouses = {w['_id']: w['name'] for w in CommercialService.get_warehouses(company_db_name)}
    accounts = FinancialService.get_bank_accounts(company_db_name)
    coupons = CouponService.get_active_coupons(company_db_name)

    db = get_company_db(company_db_name)
    sellers = []
    if db is not None:
        sellers = list(db['users'].find({}, {"name": 1, "email": 1}))
        for s in sellers:
            s['_id'] = str(s['_id'])

    return render_template(
        'commercial/order_detail.html',
        order=order,
        warehouse_name=warehouses.get(order.get('warehouse_id'), order.get('warehouse_id')),
        accounts=accounts,
        coupons=coupons,
        sellers=sellers
    )

@commercial_bp.route('/orders/<order_id>/verify-item', methods=['POST'])
def verify_order_item(order_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = OrderService.verify_order_item(
        company_db_name, order_id, request.form.get('product_id'), request.form.get('verified_quantity')
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.order_detail', order_id=order_id))

@commercial_bp.route('/orders/<order_id>/mark-ready', methods=['POST'])
def mark_order_ready(order_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = OrderService.mark_ready_to_invoice(company_db_name, order_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.order_detail', order_id=order_id))

@commercial_bp.route('/orders/<order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = OrderService.cancel_order(company_db_name, order_id, request.form.get('reason', ''))
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.order_detail', order_id=order_id))

@commercial_bp.route('/orders/<order_id>/convert', methods=['POST'])
def convert_order(order_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    overrides = {
        "doc_type": request.form.get('doc_type', '').strip(),
        "currency": request.form.get('currency', '').strip(),
        "discount_type": request.form.get('discount_type', '').strip(),
        "discount_value": request.form.get('discount_value', '').strip(),
        "coupon_code": request.form.get('coupon_code', '').strip(),
        "seller": request.form.get('seller', '').strip(),
        "payment_method": request.form.get('payment_method', '').strip(),
        "account_id": request.form.get('account_id', '').strip(),
    }
    success, message, invoice_id = OrderService.convert_order_to_invoice(company_db_name, order_id, user_email, overrides=overrides)
    flash(message, 'success' if success else 'danger')
    if success and invoice_id:
        return redirect(url_for('commercial.invoice_detail', invoice_id=invoice_id))
    return redirect(url_for('commercial.order_detail', order_id=order_id))

@commercial_bp.route('/products/search.json')
def search_products_json():
    """
    Buscador en vivo de artículos para los selects de Compras/Facturación/
    Pedidos — sin 'q' trae solo los primeros `limit` (de referencia), con 'q'
    filtra en el servidor. Así el navegador nunca carga el catálogo completo.
    """
    company_db_name = get_active_company_db()
    if not company_db_name:
        return jsonify({"results": []}), 401

    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    products, _ = CommercialService.get_paginated_products(
        company_db_name, filters={'search': q}, page=1, per_page=limit
    )
    return jsonify({"results": products})

@commercial_bp.route('/clients/search.json')
def search_clients_json():
    """Buscador en vivo de clientes para los selects de Facturación/Pedidos."""
    company_db_name = get_active_company_db()
    if not company_db_name:
        return jsonify({"results": []}), 401

    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    clients, _ = ClientService.get_paginated_clients(
        company_db_name, filters={'search': q}, page=1, per_page=limit
    )
    return jsonify({"results": clients})

@commercial_bp.route('/products/export')
def export_products():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'brand': request.args.get('brand', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'stock_filter': request.args.get('stock_filter', ''),
    }
    # A diferencia de la vista paginada, un export trae TODO lo que matchea el
    # filtro (es una acción explícita del usuario, no una carga de página).
    products_list, _ = CommercialService.get_paginated_products(company_db_name, filters=filters, page=1, per_page=100000)

    if export_format == 'pdf':
        headers = ['Nombre', 'SKU', 'Categoría', 'Marca', 'Costo', 'Precio', 'Margen %', 'Stock', 'Mínimo', 'Unidad']
        rows = [[
            p.get('name', ''), p.get('sku', ''), p.get('category', ''), p.get('brand', ''),
            f"${p.get('cost', 0):.2f}", f"${p.get('price', 0):.2f}", f"{p.get('profit_margin', 0):.1f}%",
            str(p.get('stock', 0)), str(p.get('min_stock', 0)), p.get('unit_type', ''),
        ] for p in products_list]
        pdf_bytes = generate_table_pdf("Catálogo de Productos", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="catalogo_productos.pdf"'})

    headers_map = {
        'name': 'Nombre', 'sku': 'SKU', 'category': 'Categoría', 'brand': 'Marca',
        'cost': 'Costo', 'price': 'Precio', 'profit_margin': 'Margen %',
        'stock': 'Stock', 'min_stock': 'Mínimo', 'unit_type': 'Unidad',
    }
    csv_bytes = rows_to_csv(products_list, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="catalogo_productos.csv"'})

@commercial_bp.route('/purchases')
def purchases():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15
    filters = {
        'search': request.args.get('search', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }

    orders, total_count = CommercialService.get_paginated_purchase_orders(company_db_name, filters=filters, page=page, per_page=per_page)
    warehouses = CommercialService.get_warehouses(company_db_name)

    return render_template(
        'commercial/purchases.html',
        orders=orders,
        warehouses=warehouses,
        filters=filters,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/purchases/export')
def export_purchases():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'search': request.args.get('search', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    orders_list, _ = CommercialService.get_paginated_purchase_orders(company_db_name, filters=filters, page=1, per_page=100000)

    for o in orders_list:
        o['timestamp_str'] = o.get('timestamp').strftime('%Y-%m-%d %H:%M') if o.get('timestamp') else ''

    if export_format == 'pdf':
        headers = ['Fecha', 'Artículo', 'SKU', 'Proveedor', 'Almacén', 'Cantidad', 'Costo Unit.', 'Costo Total']
        rows = [[
            o.get('timestamp_str', ''), o.get('product_name', ''), o.get('product_sku', ''), o.get('supplier_name', ''),
            o.get('warehouse_name', ''), str(o.get('quantity', 0)), f"${o.get('unit_cost', 0):.2f}", f"${o.get('total_cost', 0):.2f}",
        ] for o in orders_list]
        pdf_bytes = generate_table_pdf("Órdenes de Compra", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="compras.pdf"'})

    headers_map = {
        'timestamp_str': 'Fecha', 'product_name': 'Artículo', 'product_sku': 'SKU', 'supplier_name': 'Proveedor',
        'warehouse_name': 'Almacén', 'quantity': 'Cantidad', 'unit_cost': 'Costo Unit.', 'total_cost': 'Costo Total', 'user': 'Usuario',
    }
    csv_bytes = rows_to_csv(orders_list, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="compras.csv"'})

@commercial_bp.route('/purchases/save', methods=['POST'])
def save_purchase():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = CommercialService.register_purchase_order(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.purchases'))

@commercial_bp.route('/invoicing')
def invoicing():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15
    filters = {
        'search': request.args.get('search', ''),
        'status': request.args.get('status', ''),
        'seller': request.args.get('seller', ''),
        'doc_type': request.args.get('doc_type', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }

    invoices, total_count = InvoicingService.get_paginated_invoices(company_db_name, filters=filters, page=page, per_page=per_page)
    warehouses = CommercialService.get_warehouses(company_db_name)
    accounts = FinancialService.get_bank_accounts(company_db_name)
    summary = InvoicingService.get_sales_summary(company_db_name)
    coupons = CouponService.get_active_coupons(company_db_name)

    db = get_company_db(company_db_name)
    sellers = []
    if db is not None:
        sellers = list(db['users'].find({}, {"name": 1, "email": 1}))
        for s in sellers:
            s['_id'] = str(s['_id'])

    return render_template(
        'commercial/invoicing.html',
        invoices=invoices,
        warehouses=warehouses,
        accounts=accounts,
        summary=summary,
        coupons=coupons,
        sellers=sellers,
        filters=filters,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/invoicing/export')
def export_invoices():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'search': request.args.get('search', ''),
        'status': request.args.get('status', ''),
        'seller': request.args.get('seller', ''),
        'doc_type': request.args.get('doc_type', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    invoices_list, _ = InvoicingService.get_paginated_invoices(company_db_name, filters=filters, page=1, per_page=100000)

    for inv in invoices_list:
        inv['created_at_str'] = inv.get('created_at', '')[:16].replace('T', ' ') if inv.get('created_at') else ''
        inv['doc_type_label'] = 'Nota de Entrega' if inv.get('doc_type') == 'nota_entrega' else 'Factura Fiscal'

    if export_format == 'pdf':
        headers = ['N° Factura', 'Fecha', 'Cliente', 'RIF', 'Documento', 'Subtotal', 'IVA', 'Total', 'Moneda', 'Estado']
        rows = [[
            inv.get('invoice_number', ''), inv.get('created_at_str', ''), inv.get('client_name', ''), inv.get('client_rif', ''),
            inv.get('doc_type_label', ''), f"{inv.get('subtotal', 0):.2f}", f"{inv.get('iva_total', 0):.2f}",
            f"{inv.get('total', 0):.2f}", inv.get('currency', 'USD'), inv.get('status', '').upper(),
        ] for inv in invoices_list]
        pdf_bytes = generate_table_pdf("Facturas Emitidas", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="facturas.pdf"'})

    headers_map = {
        'invoice_number': 'N° Factura', 'created_at_str': 'Fecha', 'client_name': 'Cliente', 'client_rif': 'RIF',
        'doc_type_label': 'Documento', 'payment_method': 'Método de Pago', 'subtotal': 'Subtotal',
        'iva_total': 'IVA', 'total': 'Total', 'currency': 'Moneda', 'status': 'Estado', 'seller': 'Vendedor',
    }
    csv_bytes = rows_to_csv(invoices_list, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="facturas.csv"'})

@commercial_bp.route('/invoicing/save', methods=['POST'])
def save_invoice():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message, invoice_id = InvoicingService.create_invoice(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    if success and invoice_id:
        return redirect(url_for('commercial.invoice_detail', invoice_id=invoice_id))
    return redirect(url_for('commercial.invoicing'))

@commercial_bp.route('/invoicing/<invoice_id>')
def invoice_detail(invoice_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    invoice = InvoicingService.get_invoice(company_db_name, invoice_id)
    if not invoice:
        flash("Factura no encontrada.", "danger")
        return redirect(url_for('commercial.invoicing'))

    return render_template('commercial/invoice_detail.html', invoice=invoice)

@commercial_bp.route('/invoicing/<invoice_id>/mark-delivered', methods=['POST'])
def mark_invoice_delivered(invoice_id):
    """Respaldo manual del sello de entrega: además de llamarse desde el
    detalle de la factura, la Bandeja de Comisiones la usa directamente sobre
    cada cobro marcado "sin entrega" para no obligar a ir a buscar la
    factura — por eso el destino del redirect es configurable (`next`), no
    fijo al detalle de factura."""
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    actor_email = session.get('user_email', 'admin@gestion360.com')
    success, message = InvoicingService.mark_delivered(company_db_name, invoice_id, actor_email)
    flash(message, 'success' if success else 'danger')

    next_url = request.form.get('next', '').strip()
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(url_for('commercial.invoice_detail', invoice_id=invoice_id))

@commercial_bp.route('/commissions')
def commissions():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    filters = {
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    summary = CommissionService.get_commission_summary(company_db_name, filters=filters)
    sellers, routes, _ = _get_filter_options(company_db_name)

    return render_template(
        'commercial/commissions.html',
        summary=summary,
        filters=filters,
        sellers=sellers,
        routes=routes,
    )

@commercial_bp.route('/commissions/export')
def export_commissions():
    """
    Sin filtro de vendedor: resumen gerencial por vendedor (PDF) o el detalle
    crudo de todos los cobros (Excel/CSV). Con un vendedor filtrado: un
    recibo formal de ESE vendedor y ese período — el documento pensado para
    imprimir y entregarle como constancia de lo que se le está pagando.
    """
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = {
        'seller': request.args.get('seller', ''),
        'route_number': request.args.get('route_number', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }
    summary = CommissionService.get_commission_summary(company_db_name, filters=filters)
    period_label = f"{filters['date_from'] or 'inicio'} a {filters['date_to'] or 'hoy'}"
    company_name = session.get('company_name', 'Gestión 360')
    company_rif = session.get('company_rif', '')

    if export_format == 'pdf':
        if filters['seller']:
            seller_name = filters['seller']
            db = get_company_db(company_db_name)
            if db is not None:
                seller_doc = db['users'].find_one({"email": filters['seller']}, {"name": 1})
                if seller_doc:
                    seller_name = seller_doc.get('name', filters['seller'])
            pdf_bytes = generate_commission_receipt_pdf(
                company_name, company_rif, seller_name, period_label,
                summary['events'], summary['total_commission_usd'], summary['total_collected_usd']
            )
            return Response(pdf_bytes, mimetype='application/pdf',
                             headers={'Content-Disposition': f'attachment; filename="comision_{seller_name}_{filters["date_from"] or "inicio"}_{filters["date_to"] or "hoy"}.pdf"'})

        headers = ['Vendedor', 'Cobros', 'Pend. Entrega', 'Pend. Tasa', 'Cobrado USD', 'Comisión USD']
        rows = [[
            b['seller'], str(b['event_count']), str(b['pending_delivery_count']), str(b['pending_fx_count']),
            f"{b['total_collected_usd']:.2f}", f"{b['total_commission_usd']:.2f}",
        ] for b in summary['by_seller']]
        pdf_bytes = generate_table_pdf("Comisiones por Vendedor", company_name, headers, rows, subtitle=f"Período: {period_label}")
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="comisiones_por_vendedor.pdf"'})

    headers_map = {
        'invoice_number': 'Factura', 'client_name': 'Cliente', 'seller': 'Vendedor', 'route_number': 'Ruta',
        'delivered_at_str': 'Entregado', 'collected_at_str': 'Cobrado', 'days_elapsed': 'Días',
        'commission_rate': 'Tasa %', 'amount_usd': 'Cobrado USD', 'commission_usd': 'Comisión USD',
    }
    events = summary['events']
    for e in events:
        e['delivered_at_str'] = e['delivered_at'].strftime('%Y-%m-%d') if e.get('delivered_at') else ''
        e['collected_at_str'] = e['collected_at'].strftime('%Y-%m-%d') if e.get('collected_at') else ''
        for key in ('days_elapsed', 'commission_rate', 'amount_usd', 'commission_usd', 'route_number'):
            if e.get(key) is None:
                e[key] = ''
    csv_bytes = rows_to_csv(events, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="comisiones.csv"'})

@commercial_bp.route('/coupons/save', methods=['POST'])
def save_coupon():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    creator_email = session.get('user_email', 'admin@gestion360.com')
    success, message = CouponService.create_coupon(company_db_name, request.form, creator_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.invoicing'))

@commercial_bp.route('/coupons/<coupon_id>/deactivate', methods=['POST'])
def deactivate_coupon(coupon_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = CouponService.deactivate_coupon(company_db_name, coupon_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.invoicing'))

@commercial_bp.route('/invoicing/<invoice_id>/pdf')
def download_invoice_pdf(invoice_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    invoice = InvoicingService.get_invoice(company_db_name, invoice_id)
    if not invoice:
        flash("Factura no encontrada.", "danger")
        return redirect(url_for('commercial.invoicing'))

    pdf_bytes = generate_invoice_pdf(
        invoice, session.get('company_name', 'Gestión 360'), session.get('company_rif', '')
    )
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{invoice["invoice_number"]}.pdf"'}
    )

@commercial_bp.route('/invoicing/<invoice_id>/dispatch-guide')
def download_dispatch_guide(invoice_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    invoice = InvoicingService.get_invoice(company_db_name, invoice_id)
    if not invoice:
        flash("Factura no encontrada.", "danger")
        return redirect(url_for('commercial.invoicing'))

    from services.logistics_service import LogisticsService
    route_info = LogisticsService.get_route_for_invoice(company_db_name, invoice_id)

    pdf_bytes = generate_dispatch_guide_pdf(
        invoice, session.get('company_name', 'Gestión 360'), session.get('company_rif', ''), route_info=route_info
    )
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="Guia-Despacho-{invoice["invoice_number"]}.pdf"'}
    )

@commercial_bp.route('/dropi/sync', methods=['POST'])
def sync_dropi():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    DropiService.ensure_virtual_warehouse(company_db_name)
    success, message = DropiService.sync_catalog_to_marketplace()
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.products'))