from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from services.commercial_service import CommercialService
from services.pdf_service import generate_table_pdf
from services.export_service import rows_to_csv

warehouse_bp = Blueprint('warehouse_bp', __name__, url_prefix='/almacen')


def get_active_company_db():
    return session.get('company_db')


def _warehouse_filters():
    return {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'brand': request.args.get('brand', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
        'stock_filter': request.args.get('stock_filter', ''),
    }


@warehouse_bp.route('/')
def index():
    """
    Vista operativa de Almacén: stock, lotes y vencimientos por artículo, SIN
    costo/precio/margen (eso es información comercial, no de bodega). Pensada
    para el rol Almacenista, pero disponible para cualquier usuario autenticado.
    """
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15
    filters = _warehouse_filters()

    products_list, total_count = CommercialService.get_paginated_products(
        company_db_name, filters=filters, page=page, per_page=per_page, include_pricing=False
    )
    warehouses = CommercialService.get_warehouses(company_db_name)
    categories, brands = CommercialService.get_distinct_categories_and_brands(company_db_name)
    alert_counts = CommercialService.get_stock_alert_counts(company_db_name, filters.get('warehouse_id'))

    return render_template(
        'warehouse/index.html',
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


@warehouse_bp.route('/movement', methods=['POST'])
def register_movement():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'almacen@gestion360.com')
    success, message = CommercialService.register_movement(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('warehouse_bp.index'))


@warehouse_bp.route('/export')
def export_warehouse():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    export_format = request.args.get('format', 'excel')
    filters = _warehouse_filters()
    products_list, _ = CommercialService.get_paginated_products(
        company_db_name, filters=filters, page=1, per_page=100000, include_pricing=False
    )

    for p in products_list:
        nb = p.get('nearest_batch')
        p['lote_mas_proximo'] = nb.get('batch_code') if nb else (p.get('batch') or 'N/A')
        p['vencimiento_mas_proximo'] = (nb.get('exp_date') if nb else None) or p.get('expiration_date') or 'N/A'

    if export_format == 'pdf':
        headers = ['Nombre', 'SKU', 'Categoría', 'Marca', 'Stock', 'Mínimo', 'Unidad', 'Lote', 'Vencimiento']
        rows = [[
            p.get('name', ''), p.get('sku', ''), p.get('category', ''), p.get('brand', ''),
            str(p.get('stock', 0)), str(p.get('min_stock', 0)), p.get('unit_type', ''),
            str(p.get('lote_mas_proximo', '')), str(p.get('vencimiento_mas_proximo', '')),
        ] for p in products_list]
        pdf_bytes = generate_table_pdf("Reporte de Almacén (Stock & Vencimientos)", session.get('company_name', 'Gestión 360'), headers, rows)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="reporte_almacen.pdf"'})

    headers_map = {
        'name': 'Nombre', 'sku': 'SKU', 'category': 'Categoría', 'brand': 'Marca',
        'stock': 'Stock', 'min_stock': 'Mínimo', 'unit_type': 'Unidad',
        'lote_mas_proximo': 'Lote', 'vencimiento_mas_proximo': 'Vencimiento',
    }
    csv_bytes = rows_to_csv(products_list, headers_map)
    return Response(csv_bytes, mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename="reporte_almacen.csv"'})
