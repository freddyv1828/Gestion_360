from flask import Blueprint, request, jsonify
from services.business_service import register_business_logic

business_bp = Blueprint('business_bp', __name__)

@business_bp.route("/register-business", methods=["POST"])
def register_business():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Cuerpo de petición inválido"}), 400

        result, status_code = register_business_logic(data)
        return jsonify(result), status_code

    except Exception as e:
        print(f"Error crítico en ruta: {e}")
        return jsonify({"error": "Error interno del servidor."}), 500