from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.commercial_service import CommercialService

commercial_bp = Blueprint('commercial', __name__, template_folder='../../templates/commercial')

@commercial_bp.route('/')
def index():
    """
    Vista principal del módulo de Gestión Comercial y Financiera.
    Muestra el maestro de productos con filtros de búsqueda avanzados, 
    macro números gerenciales (KPIs), almacenes y control de movimientos auditables.
    """
    company_db_name = session.get('company_db')
    
    # Capturar parámetros de búsqueda y filtros desde la interfaz
    filters = {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'brand': request.args.get('brand', '')
    }
    
    # Obtener productos filtrados y almacenes activos
    products = CommercialService.get_commercial_products(company_db_name, filters=filters) if company_db_name else []
    warehouses = CommercialService.get_active_warehouses(company_db_name) if company_db_name else []
    
    # Obtener los macro números y costos (KPIs) para la gerencia y administración
    kpis = CommercialService.get_commercial_kpis(company_db_name) if company_db_name else {}
    
    return render_template(
        'commercial/index.html', 
        products=products, 
        warehouses=warehouses, 
        filters=filters,
        kpis=kpis
    )

@commercial_bp.route('/product/create', methods=['POST'])
def create_product():
    """
    Procesa la creación del maestro de productos completo desde el panel administrativo.
    """
    company_db_name = session.get('company_db')
    creator_email = session.get('user_email', 'admin@gestion360.com')
    
    success, message = CommercialService.create_commercial_product(company_db_name, request.form, creator_email)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('commercial.index'))

@commercial_bp.route('/movement/register', methods=['POST'])
def register_movement():
    """
    Registra traslados de almacén o ajustes/descargos auditables de mercancía.
    """
    company_db_name = session.get('company_db')
    user_email = session.get('user_email', session.get('user_name', 'Administrador'))
    
    success, message = CommercialService.register_auditable_movement(company_db_name, request.form, user_email)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('commercial.index'))