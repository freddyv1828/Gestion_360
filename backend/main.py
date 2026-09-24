from flask import Flask, redirect, url_for
from flask_cors import CORS
from database import db  # Importamos la conexión centralizada con pymongo
import os

app = Flask(__name__)
app.secret_key = 'gestion360_secret_key_super_segura'
CORS(app)

# --- REGISTRO DE TODOS LOS BLUEPRINTS ---
from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

from routes.personal_routes import personal_bp
app.register_blueprint(personal_bp)

from routes.business_routes import business_bp
app.register_blueprint(business_bp)

from routes.inventory_routes import inventory_bp
app.register_blueprint(inventory_bp)

from routes.commercial_routes import commercial_bp
app.register_blueprint(commercial_bp, url_prefix='/commercial')


# --- RUTA RAÍZ: Entrada oficial al sistema ---
@app.route('/')
def index():
    return redirect(url_for('auth_bp.login_view'))


# --- RUTA DE PRUEBA LOCAL DE BASE DE DATOS ---
@app.route('/test-db')
def test_db():
    try:
        # Comando ping nativo de MongoDB para verificar conectividad
        db.command('ping')
        return {"status": "success", "message": "¡Conexión exitosa a MongoDB Atlas desde local!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)