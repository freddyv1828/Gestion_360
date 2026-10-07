from functools import wraps
from datetime import datetime
import jwt as pyjwt
from flask import Blueprint, jsonify, request
from config import JWT_SECRET_KEY
from services.login_service import login_business_user
from services.marketplace_service import MarketplaceService
from services.commercial_service import CommercialService
from services.client_service import ClientService
from services.order_service import OrderService, OPEN_STATUSES
from services.budget_service import BudgetService
from services.financial_service import FinancialService

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/v1')


def jwt_required(f):
    """
    Exige 'Authorization: Bearer <jwt>', decodifica con JWT_SECRET_KEY e inyecta
    request.jwt_user. company_db SIEMPRE se resuelve del token, nunca de un
    parámetro de la URL/body, para que un vendedor jamás pueda leer el inventario
    de otra empresa suplantando el parámetro.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Token de autenticación faltante."}), 401

        token = auth_header.split(' ', 1)[1].strip()
        try:
            payload = pyjwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "El token ha expirado. Inicie sesión nuevamente."}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Token inválido."}), 401

        if not payload.get('company_db'):
            return jsonify({"error": "El token no corresponde a un usuario de empresa."}), 403

        request.jwt_user = payload
        return f(*args, **kwargs)
    return decorated


@api_bp.route('/auth/login', methods=['POST'])
def login():
    """
    Login unificado para la App Móvil. Identifica si es vendedor corporativo
    (descarga el inventario de su empresa) o cliente del marketplace.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({"error": "Correo y contraseña son obligatorios."}), 400

    result, status_code = login_business_user(email, password)
    if status_code != 200:
        return jsonify(result), status_code

    user = result.get('user', {})
    if user.get('user_type') in ('seller', 'company_staff'):
        result['inventory'] = MarketplaceService.get_company_inventory_for_seller(user.get('company_db'))

    return jsonify(result), 200


@api_bp.route('/marketplace/catalog', methods=['GET'])
def marketplace_catalog():
    """Vitrina pública sin autenticación para Guest Browsing del catálogo Dropi."""
    return jsonify({"products": MarketplaceService.get_public_catalog()}), 200


@api_bp.route('/marketplace/checkout', methods=['POST'])
def marketplace_checkout():
    """Confirma el carrito de compra, con registro/login en caliente del cliente."""
    data = request.get_json(silent=True) or {}
    success, message, payload = MarketplaceService.checkout(data)

    if not success:
        return jsonify({"error": message}), 400

    response = {"message": message}
    response.update(payload)
    return jsonify(response), 201


# ============================================================================
# APP MÓVIL DEL VENDEDOR — /api/v1/seller/*  (todos requieren JWT)
# ============================================================================

@api_bp.route('/seller/dashboard', methods=['GET'])
@jwt_required
def seller_dashboard():
    """Resumen ejecutivo para la pantalla principal del vendedor: clientes,
    pedidos abiertos, cuentas por cobrar y últimos movimientos."""
    company_db_name = request.jwt_user['company_db']
    user_email = request.jwt_user['email']

    clients_count = ClientService.count_active_clients(company_db_name)
    open_orders_count = OrderService.count_orders(
        company_db_name, created_by=user_email, statuses=OPEN_STATUSES
    )

    receivables = FinancialService.get_accounts_receivable(company_db_name)
    total_receivable = round(sum(r['balance_due'] for r in receivables), 2)

    recent_orders, _ = OrderService.get_paginated_orders(company_db_name, status='all', page=1, per_page=5)

    return jsonify({
        "clients_count": clients_count,
        "open_orders_count": open_orders_count,
        "accounts_receivable_total": total_receivable,
        "accounts_receivable_top": receivables[:5],
        "recent_orders": recent_orders,
    }), 200


@api_bp.route('/seller/clients', methods=['GET'])
@jwt_required
def seller_list_clients():
    """Búsqueda de clientes existentes para vincular en Pedidos/Presupuestos.
    Sin 'search', retorna solo los primeros `limit` (no el directorio completo —
    evita traer todos los clientes en cada apertura del formulario)."""
    company_db_name = request.jwt_user['company_db']
    search = request.args.get('search', '').strip()
    limit = request.args.get('limit', 20, type=int)
    clients, total_count = ClientService.get_paginated_clients(
        company_db_name, filters={'search': search}, page=1, per_page=limit
    )
    return jsonify({"clients": clients, "total_count": total_count}), 200


@api_bp.route('/seller/clients', methods=['POST'])
@jwt_required
def seller_create_client():
    company_db_name = request.jwt_user['company_db']
    data = request.get_json(silent=True) or {}
    success, message = ClientService.create_or_update_client(company_db_name, data, request.jwt_user['email'])
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message}), 201


@api_bp.route('/seller/products', methods=['GET'])
@jwt_required
def seller_products():
    """Catálogo paginado con filtro de almacén — ver docs/INTEGRATIONS.md."""
    company_db_name = request.jwt_user['company_db']
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    filters = {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'warehouse_id': request.args.get('warehouse_id', ''),
    }
    products, total_count = CommercialService.get_paginated_products(company_db_name, filters, page, per_page)
    return jsonify({
        "products": products,
        "pagination": {
            "page": page, "per_page": per_page, "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    }), 200


@api_bp.route('/seller/warehouses', methods=['GET'])
@jwt_required
def seller_warehouses():
    company_db_name = request.jwt_user['company_db']
    return jsonify({"warehouses": CommercialService.get_warehouses(company_db_name)}), 200


@api_bp.route('/seller/orders', methods=['GET'])
@jwt_required
def seller_list_orders():
    company_db_name = request.jwt_user['company_db']
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    orders, total_count = OrderService.get_paginated_orders(company_db_name, status=status, page=page, per_page=per_page)
    # Alcance "mis pedidos": el vendedor solo ve los que él mismo registró.
    own_only = request.args.get('mine', 'true').lower() != 'false'
    if own_only:
        orders = [o for o in orders if o.get('created_by') == request.jwt_user['email']]
    return jsonify({
        "orders": orders,
        "pagination": {
            "page": page, "per_page": per_page, "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    }), 200


@api_bp.route('/seller/orders', methods=['POST'])
@jwt_required
def seller_create_order():
    company_db_name = request.jwt_user['company_db']
    data = request.get_json(silent=True) or {}
    import json as _json
    form_like = {
        'client_id': data.get('client_id', ''),
        'client_name': data.get('client_name', ''),
        'client_rif': data.get('client_rif', ''),
        'client_email': data.get('client_email', ''),
        'warehouse_id': data.get('warehouse_id', ''),
        'doc_type': data.get('doc_type', 'factura_fiscal'),
        'comment': data.get('comment', ''),
        'items_json': _json.dumps(data.get('items', [])),
    }
    success, message, order_id = OrderService.create_order(company_db_name, form_like, request.jwt_user['email'])
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message, "order_id": order_id}), 201


@api_bp.route('/seller/orders/<order_id>', methods=['GET'])
@jwt_required
def seller_order_detail(order_id):
    company_db_name = request.jwt_user['company_db']
    order = OrderService.get_order(company_db_name, order_id)
    if not order:
        return jsonify({"error": "Pedido no encontrado."}), 404
    return jsonify({"order": order}), 200


@api_bp.route('/seller/orders/<order_id>/cancel', methods=['POST'])
@jwt_required
def seller_cancel_order(order_id):
    company_db_name = request.jwt_user['company_db']
    data = request.get_json(silent=True) or {}
    success, message = OrderService.cancel_order(company_db_name, order_id, data.get('reason', ''))
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message}), 200


@api_bp.route('/seller/budgets', methods=['GET'])
@jwt_required
def seller_list_budgets():
    company_db_name = request.jwt_user['company_db']
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    budgets, total_count = BudgetService.get_paginated_budgets(
        company_db_name, created_by=request.jwt_user['email'], page=page, per_page=per_page
    )
    return jsonify({
        "budgets": budgets,
        "pagination": {
            "page": page, "per_page": per_page, "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    }), 200


@api_bp.route('/seller/budgets', methods=['POST'])
@jwt_required
def seller_create_budget():
    company_db_name = request.jwt_user['company_db']
    data = request.get_json(silent=True) or {}
    import json as _json
    form_like = {
        'client_id': data.get('client_id', ''),
        'client_name': data.get('client_name', ''),
        'client_rif': data.get('client_rif', ''),
        'comment': data.get('comment', ''),
        'items_json': _json.dumps(data.get('items', [])),
    }
    success, message, budget_id = BudgetService.create_budget(company_db_name, form_like, request.jwt_user['email'])
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message, "budget_id": budget_id}), 201


@api_bp.route('/seller/budgets/<budget_id>/convert', methods=['POST'])
@jwt_required
def seller_convert_budget(budget_id):
    company_db_name = request.jwt_user['company_db']
    data = request.get_json(silent=True) or {}
    success, message, order_id = BudgetService.convert_budget_to_order(
        company_db_name, budget_id, data.get('warehouse_id', ''), data.get('doc_type', 'factura_fiscal'),
        request.jwt_user['email']
    )
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message, "order_id": order_id}), 200


@api_bp.route('/seller/accounts-receivable', methods=['GET'])
@jwt_required
def seller_accounts_receivable():
    company_db_name = request.jwt_user['company_db']
    return jsonify({"receivables": FinancialService.get_accounts_receivable(company_db_name)}), 200
