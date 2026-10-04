# backend/routes/auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from services.login_service import login_business_user

auth_bp = Blueprint('auth_bp', __name__)

# 1. Portada / Login principal
@auth_bp.route("/", methods=["GET"])
def index():
    if session.get('company_db') and session.get('user_email'):
        return redirect(url_for('auth_bp.dashboard_view'))
    return render_template("login.html")

# 2. Procesar Login (Soporta Formulario Web y Peticiones JSON de la App Móvil)
@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    if request.is_json:
        data = request.get_json() or {}
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
    else:
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

    result, status_code = login_business_user(email, password)

    if status_code == 200:
        user_data = result.get("user", {})
        session['user_email'] = user_data.get("email")
        session['user_name'] = user_data.get("name", "Usuario")
        session['user_role'] = user_data.get("role", "admin")
        session['user_type'] = user_data.get("user_type", "company_staff")
        session['company_rif'] = user_data.get("rif")
        session['company_name'] = user_data.get("business_name")
        session['company_db'] = user_data.get("company_db")
        session['jwt_token'] = result.get("token")

        if request.is_json:
            return jsonify(result), 200

        return redirect(url_for("auth_bp.dashboard_view"))
    else:
        if request.is_json:
            return jsonify(result), status_code

        error_msg = result.get("error", "Error de autenticación.")
        return f"""
        <html>
            <body style='background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:50px;'>
                <h1 style='color:#f87171;'>Acceso Denegado</h1>
                <p style='font-size: 18px;'>{error_msg}</p>
                <br><a href='/' style='color:#38bdf8; text-decoration:none; font-weight:bold;'>← Volver al login</a>
            </body>
        </html>
        """, status_code

# 3. Cerrar Sesión Corporativa
@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth_bp.index"))

# 4. Vista HTML del Formulario de Registro Comercial
@auth_bp.route("/register-business", methods=["GET"])
def register_business_view():
    return render_template("register_business.html")

# 5. Panel Administrativo (Dashboard)
@auth_bp.route("/dashboard", methods=["GET"])
def dashboard_view():
    if not session.get('company_db') or not session.get('user_email'):
        return redirect(url_for('auth_bp.index'))

    company_name = session.get('company_name', "Gestión 360")
    user_name = session.get('user_name', "Administrador")
    user_role = session.get('user_role', "admin")
    company_db_name = session.get('company_db')

    metrics = {
        "staff_count": 0,
        "products_count": 0,
        "warehouses_count": 0,
        "purchases_count": 0,
        "invoices_count": 0,
        "vehicles_count": 0,
    }
    try:
        from database import get_company_db
        db = get_company_db(company_db_name)
        if db is not None:
            metrics["staff_count"] = db['users'].count_documents({})
            metrics["products_count"] = db['products'].count_documents({"is_active": {"$ne": False}})
            metrics["warehouses_count"] = db['warehouses'].count_documents({"is_active": {"$ne": False}})
            metrics["purchases_count"] = db['purchase_orders'].count_documents({})
            metrics["invoices_count"] = db['invoices'].count_documents({"status": "emitida"})
            metrics["vehicles_count"] = db['vehicles'].count_documents({"is_active": {"$ne": False}})
    except Exception as e:
        print(f"Error cargando métricas en dashboard: {e}")

    return render_template(
        "dashboard.html",
        company_name=company_name,
        user_name=user_name,
        user_role=user_role,
        metrics=metrics
    )