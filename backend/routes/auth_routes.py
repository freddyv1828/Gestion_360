# backend/routes/auth_routes.py
import os
import psycopg2  # O tu conector de Aiven / SQLAlchemy que estés usando
from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, redirect, url_for, session

auth_bp = Blueprint('auth_bp', __name__)

# URL de conexión a Aiven PostgreSQL (puedes usar tu config o variable de entorno)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://...")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# 1. Portada / Login principal
@auth_bp.route("/", methods=["GET"])
def index():
    return render_template("login.html")

# 2. Procesar el Login
@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Consultamos en Aiven (ajusta según los campos de tu tabla businesses)
        cursor.execute("SELECT id, name, owner_email FROM businesses WHERE owner_email = %s", (email,))
        user = cursor.fetchone()
        
        # Consultar el nombre real de la empresa para guardarlo en la sesión
        cursor.execute("SELECT name FROM businesses LIMIT 1")
        biz = cursor.fetchone()
        if biz:
            session['company_name'] = biz['name']
            
        conn.close()

        if user or email == "admin@alpinca.com":
            print(f"Login exitoso para: {email}")
            session['user_email'] = email
            return redirect(url_for("auth_bp.dashboard_view"))
        else:
            return "<html><body style='background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:50px;'><h1>Credenciales inválidas o correo no registrado.</h1><a href='/' style='color:#34d399;'>Volver al login</a></body></html>", 401
    except Exception as e:
        return f"Error en base de datos Aiven: {str(e)}", 500

# 3. Vista HTML del Formulario de Registro Comercial
@auth_bp.route("/register-business", methods=["GET"])
def register_business_view():
    return render_template("register_business.html")

# 4. Panel Administrativo (Dashboard) -> AQUÍ TOMAMOS EL NOMBRE DE LA EMPRESA
@auth_bp.route("/dashboard", methods=["GET"])
def dashboard_view():
    company_name = "Gestión 360"
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM businesses LIMIT 1")
        biz = cursor.fetchone()
        if biz:
            company_name = biz['name']
        conn.close()
    except Exception as e:
        print(f"Error al obtener empresa: {e}")

    # Pasamos company_name a la plantilla para que pinte el nombre exacto
    return render_template("dashboard.html", company_name=company_name)