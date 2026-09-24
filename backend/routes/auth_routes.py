# backend/routes/auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session

# Importamos la lógica centralizada de login que valida contra MongoDB
from services.login_service import login_business_user

auth_bp = Blueprint('auth_bp', __name__)

# 1. Portada / Login principal
@auth_bp.route("/", methods=["GET"])
def index():
    return render_template("login.html")

# 2. Procesar el Login utilizando la validación centralizada SaaS
@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    # Llamamos a nuestro servicio centralizado
    result, status_code = login_business_user(email, password)

    if status_code == 200:
        # Guardamos los datos clave en la sesión de Flask para el multi-tenant
        user_data = result.get("user", {})
        session['user_email'] = user_data.get("email")
        session['company_name'] = user_data.get("business_name")
        session['company_db'] = user_data.get("company_db")  # Base de datos aislada en MongoDB
        session['user_role'] = user_data.get("role")
        
        print(f"Login exitoso para: {email} en la empresa: {session['company_name']}")
        return redirect(url_for("auth_bp.dashboard_view"))
    else:
        # Si la licencia expiró, está suspendida o las credenciales fallan, mostramos el error
        error_msg = result.get("error", "Error de autenticación.")
        return f"""
        <html>
            <body style='background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:50px;'>
                <h1 style='color:#f87171;'>Acceso Denegado</h1>
                <p style='font-size: 18px;'>{error_msg}</p>
                <br><a href='/' style='color:#34d399; text-decoration:none; font-weight:bold;'>Volver al login</a>
            </body>
        </html>
        """, status_code

# 3. Vista HTML del Formulario de Registro Comercial
@auth_bp.route("/register-business", methods=["GET"])
def register_business_view():
    return render_template("register_business.html")

# 4. Panel Administrativo (Dashboard) -> Muestra el nombre de la empresa activa desde la sesión
@auth_bp.route("/dashboard", methods=["GET"])
def dashboard_view():
    # Tomamos el nombre directamente de la sesión si ya está logueado
    company_name = session.get('company_name', "Gestión 360")

    # Pasamos company_name a la plantilla para que pinte el nombre exacto de la compañía
    return render_template("dashboard.html", company_name=company_name)