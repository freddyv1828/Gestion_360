from flask import Flask, redirect, url_for
from flask_cors import CORS
from database import db
from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# --- REGISTRO DE BLUEPRINTS ---
from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

from routes.personal_routes import personal_bp
app.register_blueprint(personal_bp)

from routes.commercial_routes import commercial_bp
app.register_blueprint(commercial_bp, url_prefix='/commercial')

from routes.logistics_routes import logistics_bp
app.register_blueprint(logistics_bp)

from routes.api_routes import api_bp
app.register_blueprint(api_bp)

# --- RUTA RAÍZ: Entrada oficial al sistema ---
@app.route('/')
def index():
    return redirect(url_for('auth_bp.index'))

# --- RUTA DE VERIFICACIÓN DE CONEXIÓN A BASE DE DATOS ---
@app.route('/test-db')
def test_db():
    try:
        db.command('ping')
        return {"status": "success", "message": "¡Conexión exitosa a MongoDB Atlas!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)