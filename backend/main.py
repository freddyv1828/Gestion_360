from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = 'gestion360_secret_key_super_segura'

# Cargamos la configuración desde tu archivo config.py
app.config.from_object('config')

# Inicializamos SQLAlchemy con la configuración existente de Aiven
db = SQLAlchemy(app)

# --- REGISTRO DE TODOS LOS BLUEPRINTS ---
from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

from routes.personal_routes import personal_bp
app.register_blueprint(personal_bp)

from routes.business_routes import business_bp
app.register_blueprint(business_bp)

# 🚀 ¡AQUÍ ESTABA FALTANDO REGISTRAR EL INVENTARIO!
from routes.inventory_routes import inventory_bp
app.register_blueprint(inventory_bp)


# --- RUTA RAÍZ: Entrada oficial al sistema ---
@app.route('/')
def index():
    # Por defecto redirige al login que maneja auth_routes
    return redirect(url_for('auth_bp.login_view'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)