from flask import Flask, redirect, url_for, session, request, flash
from flask_cors import CORS
from database import db
from config import SECRET_KEY
from rbac import get_allowed_modules, module_for_path

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)


@app.before_request
def enforce_module_access():
    """Bloqueo de acceso por rol a nivel de servidor (no solo de menú/UI): si
    la sesión activa no tiene el módulo de la ruta solicitada entre sus
    módulos permitidos, se corta aquí mismo. Antes de esto, un Almacenista
    podía entrar a Finanzas/Personal con solo escribir la URL."""
    if 'company_db' not in session:
        return None  # sin sesión de empresa activa -> lo resuelve cada vista (redirect a login)

    module = module_for_path(request.path)
    if module is None:
        return None

    allowed = get_allowed_modules(session.get('user_role'))
    if module not in allowed:
        flash("Tu rol no tiene acceso a esta sección.", "danger")
        return redirect(url_for('auth_bp.dashboard_view'))
    return None


@app.context_processor
def inject_allowed_modules():
    """Para que base.html pueda ocultar del menú las secciones que el rol
    actual no puede abrir, en vez de solo bloquearlas al hacer clic. Siempre
    expone la variable (con acceso completo por defecto) para que la
    plantilla nunca se tope con un Undefined de Jinja."""
    if 'company_db' not in session:
        return {"allowed_modules": get_allowed_modules(None)}
    return {"allowed_modules": get_allowed_modules(session.get('user_role'))}

# --- REGISTRO DE BLUEPRINTS ---
from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

from routes.personal_routes import personal_bp
app.register_blueprint(personal_bp)

from routes.commercial_routes import commercial_bp
app.register_blueprint(commercial_bp, url_prefix='/commercial')

from routes.logistics_routes import logistics_bp
app.register_blueprint(logistics_bp)

from routes.warehouse_routes import warehouse_bp
app.register_blueprint(warehouse_bp)

from routes.api_routes import api_bp
app.register_blueprint(api_bp)

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