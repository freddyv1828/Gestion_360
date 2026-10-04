from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.logistics_service import LogisticsService

logistics_bp = Blueprint('logistics_bp', __name__, url_prefix='/logistics')

def get_active_company_db():
    """Retorna la base de datos de la empresa desde la sesión activa de forma segura."""
    return session.get('company_db')

@logistics_bp.route('/')
def index():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 15

    vehicles = LogisticsService.get_vehicles(company_db_name)
    drivers = LogisticsService.get_available_drivers(company_db_name)
    routes, total_count = LogisticsService.get_routes(company_db_name, page=page, per_page=per_page)

    return render_template(
        'logistics/index.html',
        vehicles=vehicles,
        drivers=drivers,
        routes=routes,
        pagination={
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page if total_count > 0 else 1
        }
    )

@logistics_bp.route('/vehicles/save', methods=['POST'])
def save_vehicle():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = LogisticsService.create_vehicle(company_db_name, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('logistics_bp.index'))

@logistics_bp.route('/routes/save', methods=['POST'])
def save_route():
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    user_email = session.get('user_email', 'admin@gestion360.com')
    success, message = LogisticsService.create_route(company_db_name, request.form, user_email)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('logistics_bp.index'))

@logistics_bp.route('/routes/<route_id>/status', methods=['POST'])
def update_route_status(route_id):
    company_db_name = get_active_company_db()
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    new_status = request.form.get('status', '').strip()
    success, message = LogisticsService.update_route_status(company_db_name, route_id, new_status)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('logistics_bp.index'))
