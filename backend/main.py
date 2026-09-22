import os
import sqlite3
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_cors import CORS
from routes.business_routes import business_bp

app = Flask(__name__)
CORS(app)

# Registrar Blueprints de rutas de la API
app.register_blueprint(business_bp)

DB_PATH = os.path.join(os.path.dirname(__file__), 'gestion360.db')

# 1. Portada / Login principal
@app.route("/", methods=["GET"])
def index():
    return render_template("login.html")

# 2. Procesar el Login (¡Aquí estaba el 404!)
@app.route("/api/login", methods=["POST"])
def api_login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    # Validación rápida contra la base de datos local SQLite de empresas registradas
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, owner_email FROM businesses WHERE owner_email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user or email == "admin@alpinca.com":  # Acceso de respaldo o por empresa registrada
            print(f"Login exitoso para: {email}")
            return redirect(url_for("dashboard_view"))
        else:
            return "<html><body style='background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:50px;'><h1>Credenciales inválidas o correo no registrado.</h1><a href='/' style='color:#34d399;'>Volver al login</a></body></html>", 401
    except Exception as e:
        return f"Error en base de datos local: {str(e)}", 500

# 3. Vista HTML del Formulario de Registro Comercial
@app.route("/register-business", methods=["GET"])
def register_business_view():
    return render_template("register_business.html")

# 4. Panel Administrativo (Dashboard)
@app.route("/dashboard", methods=["GET"])
def dashboard_view():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))