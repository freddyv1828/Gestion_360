from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from services.commercial_service import CommercialService
from services.dropi_service import DropiService
from services.financial_service import FinancialService
from services.invoicing_service import InvoicingService
from services.client_service import ClientService
from services.exchange_rate_service import ExchangeRateService
from services.order_service import OrderService
from services.coupon_service import CouponService
from services.pdf_service import generate_invoice_pdf, generate_dispatch_guide_pdf, generate_table_pdf
from services.export_service import rows_to_csv
from database import get_company_db
from rbac import is_warehouse_only_role

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
    receivables = FinancialService.get_accounts_receivable(company_db_name)

    return render_template(
        'commercial/financial.html',
        settings=settings,
        rates=rates,
        accounts=accounts,
        transactions=transactions,
        summary=summary,
        receivables=receivables
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

@commercial_bp.route('/financial/rates/sync-bcv', methods=['POST'])
def sync_bcv_rates():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = ExchangeRateService.sync_bcv_rates(company_db_name, user_email)
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
    filters = {'search': request.args.get('search', '')}

    clients_list, total_count = ClientService.get_paginated_clients(
        company_db_name, filters=filters, page=page, per_page=per_page
    )

    return render_template(
        'commercial/clients.html',
        clients=clients_list,
        filters=filters,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@commercial_bp.route('/clients/save', methods=['POST'])
def save_client():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    creator_email = session.get('user_email', 'admin@gestion360.com')
    success, message = ClientService.create_or_update_client(company_db_name, request.form, creator_email)
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

    orders_list, total_count = OrderService.get_paginated_orders(company_db_name, status=status, page=page, per_page=per_page)
    status_counts = OrderService.get_status_counts(company_db_name)
    warehouses = CommercialService.get_warehouses(company_db_name)
    products = CommercialService.get_active_products_lite(company_db_name)
    clients = ClientService.get_active_clients_lite(company_db_name)

    return render_template(
        'commercial/orders.html',
        orders=orders_list,
        status=status,
        status_counts=status_counts,
        warehouses=warehouses,
        products=products,
        clients=clients,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

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
    clients = ClientService.get_active_clients_lite(company_db_name)
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
        products=products,
        accounts=accounts,
        summary=summary,
        clients=clients,
        coupons=coupons,
        sellers=sellers,
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