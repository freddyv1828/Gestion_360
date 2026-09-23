from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from services.inventory_service import (
    get_warehouses_service, 
    create_warehouse_service, 
    get_products_service, 
    create_product_service
)

inventory_bp = Blueprint('inventory_bp', __name__, url_prefix='/inventory')

@inventory_bp.route('/', methods=['GET'])
def inventory_view():
    """Vista principal de logística, almacenes y catálogo de productos."""
    company_name = session.get('company_name', 'Mi Empresa')
    company_rif = session.get('company_rif', 'J-00000000-0')

    warehouses = get_warehouses_service(company_rif)
    products = get_products_service(company_rif)

    return render_template(
        "inventory/index.html", 
        company_name=company_name, 
        warehouses=warehouses, 
        products=products
    )

@inventory_bp.route('/api/warehouse/create', methods=['POST'])
def create_warehouse_route():
    """Crea un nuevo almacén personalizado."""
    company_rif = session.get('company_rif', 'J-12345678-9')
    name = request.form.get('name')
    description = request.form.get('description', '')

    success, message = create_warehouse_service(company_rif, name, description)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/product/create', methods=['POST'])
def create_product_route():
    """Registra un producto en el inventario (Unidades o Kg)."""
    company_rif = session.get('company_rif', 'J-12345678-9')
    
    success, message = create_product_service(company_rif, request.form)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('inventory_bp.inventory_view'))