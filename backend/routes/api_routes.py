from flask import Blueprint, jsonify, request
from services.login_service import login_business_user
from services.marketplace_service import MarketplaceService

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/v1')


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
