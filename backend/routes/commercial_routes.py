from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.commercial_service import CommercialService
from services.dropi_service import DropiService
from services.financial_service import FinancialService
from services.invoicing_service import InvoicingService
from database import get_company_db

commercial_bp = Blueprint('commercial', __name__, template_folder='../../templates/commercial')

def get_active_company_db():
    """Retorna la base de datos de la empresa desde la sesión activa de forma segura."""
    return session.get('company_db')

@commercial_bp.route('/')
def index():
    return redirect(url_for('commercial.financial'))

@commercial_bp.route('/financial')
def financial():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    settings = FinancialService.get_company_settings(company_db_name)
    rates = FinancialService.get_latest_rates(company_db_name)
    accounts = FinancialService.get_bank_accounts(company_db_name)
    transactions = FinancialService.get_recent_transactions(company_db_name)
    summary = FinancialService.get_reconciliation_summary(company_db_name)

    return render_template(
        'commercial/financial.html',
        settings=settings,
        rates=rates,
        accounts=accounts,
        transactions=transactions,
        summary=summary
    )

@commercial_bp.route('/financial/currency/save', methods=['POST'])
def save_base_currency():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = FinancialService.update_base_currency(company_db_name, request.form.get('base_currency'))
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.financial'))

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
    return redirect(url_for('commercial.financial'))

@commercial_bp.route('/financial/accounts/save', methods=['POST'])
def save_bank_account():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = FinancialService.create_bank_account(company_db_name, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.financial'))

@commercial_bp.route('/financial/transaction/save', methods=['POST'])
def save_treasury_transaction():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = FinancialService.register_transaction(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.financial'))

@commercial_bp.route('/products')
def products():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    filters = {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'brand': request.args.get('brand', ''),
        'warehouse_id': request.args.get('warehouse_id', '')
    }
    
    products_list, total_count = CommercialService.get_paginated_products(
        company_db_name, filters=filters, page=page, per_page=per_page
    )

    warehouses = CommercialService.get_warehouses(company_db_name)
    alert_counts = CommercialService.get_stock_alert_counts(company_db_name, filters.get('warehouse_id'))

    return render_template(
        'commercial/products.html',
        products=products_list,
        warehouses=warehouses,
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

@commercial_bp.route('/purchases')
def purchases():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15

    orders, total_count = CommercialService.get_paginated_purchase_orders(company_db_name, page=page, per_page=per_page)
    warehouses = CommercialService.get_warehouses(company_db_name)
    products = CommercialService.get_active_products_lite(company_db_name)

    return render_template(
        'commercial/purchases.html',
        orders=orders,
        warehouses=warehouses,
        products=products,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

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

    invoices, total_count = InvoicingService.get_paginated_invoices(company_db_name, page=page, per_page=per_page)
    warehouses = CommercialService.get_warehouses(company_db_name)
    products = CommercialService.get_active_products_lite(company_db_name)
    accounts = FinancialService.get_bank_accounts(company_db_name)
    summary = InvoicingService.get_sales_summary(company_db_name)

    return render_template(
        'commercial/invoicing.html',
        invoices=invoices,
        warehouses=warehouses,
        products=products,
        accounts=accounts,
        summary=summary,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

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

@commercial_bp.route('/dropi/sync', methods=['POST'])
def sync_dropi():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    DropiService.ensure_virtual_warehouse(company_db_name)
    success, message = DropiService.sync_catalog_to_marketplace()
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('commercial.products'))