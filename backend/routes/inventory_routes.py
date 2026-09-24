# backend/routes/inventory_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from functools import wraps
from bson import ObjectId
from database import get_company_db
from services.inventory_service import (
    get_warehouses_service, 
    create_warehouse_service, 
    update_warehouse_service,
    delete_warehouse_service,
    get_products_service, 
    create_product_service,
    update_product_service,
    delete_product_service
)

inventory_bp = Blueprint('inventory_bp', __name__, url_prefix='/inventory')

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('user_role', 'operador').lower()
            if user_role not in [r.lower() for r in allowed_roles]:
                flash("Acceso denegado: No tienes permisos suficientes para realizar esta acción.", "danger")
                return redirect(url_for('inventory_bp.inventory_view'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@inventory_bp.route('/', methods=['GET'])
def inventory_view():
    company_name = session.get('company_name', 'Mi Empresa')
    company_db_name = session.get('company_db')

    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    warehouses = get_warehouses_service(company_db_name)
    products = get_products_service(company_db_name)

    return render_template(
        "inventory/index.html", 
        company_name=company_name, 
        warehouses=warehouses, 
        products=products
    )

@inventory_bp.route('/warehouse/<warehouse_name>', methods=['GET'])
def warehouse_detail_view(warehouse_name):
    company_name = session.get('company_name', 'Mi Empresa')
    company_db_name = session.get('company_db')

    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    warehouses = get_warehouses_service(company_db_name)
    db = get_company_db(company_db_name)
    batches_col = db['inventory_batches']
    products_col = db['products']
    
    # Búsqueda flexible de lotes por nombre de almacén
    warehouse_batches = list(batches_col.find({
        "$or": [
            {"warehouse": warehouse_name},
            {"warehouse_name": warehouse_name}
        ]
    }))
    
    for batch in warehouse_batches:
        batch['_id'] = str(batch['_id'])
        prod_id = batch.get('product_id')
        prod = None
        if prod_id:
            try:
                prod = products_col.find_one({"_id": ObjectId(prod_id)})
            except:
                prod = products_col.find_one({"_id": prod_id})
                
        batch['product_name'] = prod.get('name', 'Producto Desconocido') if prod else 'Desconocido'
        batch['sku'] = prod.get('sku', 'N/D') if prod else 'N/D'
        batch['batch'] = batch.get('batch') or batch.get('batch_number') or 'S/N'
        batch['expiration_date'] = batch.get('expiration_date') or batch.get('vencimiento') or 'N/D'

    return render_template(
        "inventory/warehouse_detail.html", 
        company_name=company_name, 
        warehouses=warehouses, 
        selected_warehouse=warehouse_name,
        batches=warehouse_batches
    )

@inventory_bp.route('/api/warehouse/create', methods=['POST'])
@role_required(['admin', 'gerente'])
def create_warehouse_route():
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    name = request.form.get('name')
    description = request.form.get('description', '')
    is_available_for_sale = True if request.form.get('is_available_for_sale') else False

    success, message = create_warehouse_service(company_db_name, name, description, is_available_for_sale)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/warehouse/update/<warehouse_id>', methods=['POST'])
@role_required(['admin', 'gerente'])
def update_warehouse_route(warehouse_id):
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    name = request.form.get('name')
    description = request.form.get('description', '')
    is_available_for_sale = True if request.form.get('is_available_for_sale') else False

    success, message = update_warehouse_service(company_db_name, warehouse_id, name, description, is_available_for_sale)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/warehouse/delete/<warehouse_id>', methods=['POST'])
@role_required(['admin'])
def delete_warehouse_route(warehouse_id):
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = delete_warehouse_service(company_db_name, warehouse_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/product/create', methods=['POST'])
@role_required(['admin', 'gerente'])
def create_product_route():
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))
    
    creator_email = session.get('user_email', session.get('email', 'admin@sistema.com'))
    success, message = create_product_service(company_db_name, request.form, creator_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/product/update/<product_id>', methods=['POST'])
@role_required(['admin', 'gerente'])
def update_product_route(product_id):
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    modifier_email = session.get('user_email', session.get('email', 'admin@sistema.com'))
    success, message = update_product_service(company_db_name, product_id, request.form, modifier_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/product/delete/<product_id>', methods=['POST'])
@role_required(['admin'])
def delete_product_route(product_id):
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = delete_product_service(company_db_name, product_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/batch/update/<batch_id>', methods=['POST'])
@role_required(['admin', 'gerente', 'supervisor', 'operador'])
def update_batch_route(batch_id):
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    db = get_company_db(company_db_name)
    batches_col = db['inventory_batches']

    new_batch_name = request.form.get('batch')
    new_expiry = request.form.get('expiration_date')

    try:
        batches_col.update_one(
            {"_id": ObjectId(batch_id)},
            {"$set": {
                "batch": new_batch_name,
                "batch_number": new_batch_name,
                "expiration_date": new_expiry
            }}
        )
        flash("Lote y fecha de vencimiento actualizados correctamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar el lote: {str(e)}", "danger")

    return redirect(request.referrer or url_for('inventory_bp.inventory_view'))

@inventory_bp.route('/api/stock/receive', methods=['POST'])
@role_required(['admin', 'gerente', 'operador'])
def receive_stock_route():
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    db = get_company_db(company_db_name)
    products_col = db['products']
    batches_col = db['inventory_batches']

    product_id = request.form.get('product_id')
    warehouse = request.form.get('warehouse') or request.form.get('source_warehouse') or 'Almacén Principal'
    quantity_str = request.form.get('quantity', '0')
    batch_name = request.form.get('batch') or request.form.get('batch_number', 'S/N')
    expiration_date = request.form.get('expiration_date', 'N/D')

    try:
        quantity = float(quantity_str)
    except ValueError:
        flash("La cantidad debe ser un valor numérico válido.", "danger")
        return redirect(url_for('inventory_bp.inventory_view'))

    if not product_id or quantity <= 0:
        flash("Debe seleccionar un producto y especificar una cantidad mayor a cero.", "danger")
        return redirect(url_for('inventory_bp.inventory_view'))

    try:
        product = products_col.find_one({"_id": ObjectId(product_id)})
        if product:
            current_stock = float(product.get('stock', 0.0))
            new_stock = current_stock + quantity

            products_col.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"stock": new_stock}}
            )

            batches_col.insert_one({
                "product_id": str(product_id),
                "warehouse": warehouse,
                "warehouse_name": warehouse,
                "quantity": quantity,
                "batch": batch_name,
                "batch_number": batch_name,
                "expiration_date": expiration_date,
                "timestamp": datetime.utcnow()
            })

            flash(f"Se han ingresado exitosamente {quantity} al almacén {warehouse}.", "success")
        else:
            flash("El producto seleccionado no existe en el inventario.", "danger")
    except Exception as e:
        flash(f"Error al registrar la recepción de stock: {str(e)}", "danger")

    return redirect(url_for('inventory_bp.inventory_view'))