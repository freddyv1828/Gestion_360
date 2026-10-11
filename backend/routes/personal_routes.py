# backend/routes/personal_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
from io import BytesIO
from bson import ObjectId
from database import get_company_db
from utils import get_r2_client, R2_BUCKET_NAME
from services.personal_service import update_employee_service, create_employee_service, seed_demo_sales_force
from services.route_service import RouteService

personal_bp = Blueprint('personal_bp', __name__, url_prefix='/personal')

@personal_bp.route('/', methods=['GET'])
def personal_view():
    """Vista principal de gestión de personal (Multi-tenant MongoDB)."""
    company_name = session.get('company_name', 'Mi Empresa')
    company_db_name = session.get('company_db')
    
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    staff_members = []
    try:
        db = get_company_db(company_db_name)
        users_col = db['users']
        
        cursor_users = users_col.find({})
        for doc in cursor_users:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            doc['id'] = doc.get('_id')
            staff_members.append(doc)
            
    except Exception as e:
        print(f"Error cargando personal desde MongoDB: {e}")

    return render_template("personal/index.html", company_name=company_name, staff_members=staff_members)

@personal_bp.route('/download-doc', methods=['GET'])
def download_doc():
    """Ruta para ver o descargar documentos almacenados en Cloudflare R2."""
    file_key = request.args.get('key')
    if not file_key:
        return "No se especificó un archivo", 400

    try:
        s3 = get_r2_client()
        response = s3.get_object(Bucket=R2_BUCKET_NAME, Key=file_key)
        file_stream = BytesIO(response['Body'].read())
        return send_file(
            file_stream,
            mimetype=response.get('ContentType', 'application/octet-stream'),
            as_attachment=False,
            download_name=file_key.split('/')[-1]
        )
    except Exception as e:
        print(f"Error al descargar archivo de R2: {e}")
        return "Archivo no encontrado o error en el servidor", 404

@personal_bp.route('/api/create', methods=['POST'])
def create_employee_route():
    """Ruta para registrar nuevo personal en la BD del tenant."""
    creator_email = session.get('user_email', 'admin@empresa.com')
    company_rif = session.get('company_rif') or session.get('company_db')

    if not company_rif:
        return redirect(url_for('auth_bp.index'))

    success, message = create_employee_service(
        form_data=request.form,
        files_data=request.files,
        creator_email=creator_email,
        company_rif=company_rif
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('personal_bp.personal_view'))

@personal_bp.route('/api/update/<string:user_id>', methods=['POST'])
def update_employee_route(user_id):
    """Ruta para modificar personal existente."""
    modifier_email = session.get('user_email', 'admin@empresa.com')
    company_rif = session.get('company_rif') or session.get('company_db')

    if not company_rif:
        return redirect(url_for('auth_bp.index'))

    # Pasamos el company_rif que exige el servicio de actualización
    success, message = update_employee_service(
        user_id=user_id,
        form_data=request.form,
        files_data=request.files,
        modifier_email=modifier_email,
        company_rif=company_rif
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('personal_bp.personal_view'))

@personal_bp.route('/seed-demo-sales-force', methods=['POST'])
def seed_demo_sales_force_route():
    """Genera (si faltan) 5 vendedores demo con ruta 1-5 y asegura ~20
    clientes repartidos entre esas rutas — para poder probar de inmediato la
    cartera de clientes por vendedor sin tener que crear todo a mano."""
    company_db_name = session.get('company_db')
    company_rif = session.get('company_rif') or company_db_name
    company_name = session.get('company_name', 'Mi Empresa')
    creator_email = session.get('user_email', 'admin@empresa.com')

    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    success, message = seed_demo_sales_force(company_db_name, creator_email, company_rif, company_name)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('personal_bp.personal_view'))

@personal_bp.route('/routes', methods=['GET'])
def routes_view():
    """Administración de rutas comerciales: alta de rutas y vendedor titular
    de cada una, como entidad fija en vez de un número suelto editable desde
    cualquier formulario."""
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    db = get_company_db(company_db_name)
    sellers = list(db['users'].find({"is_active": {"$ne": False}}, {"name": 1, "email": 1, "route_number": 1}).sort('name', 1))
    for s in sellers:
        s['_id'] = str(s['_id'])

    routes = RouteService.list_routes(company_db_name)
    return render_template('personal/routes.html', routes=routes, sellers=sellers)

@personal_bp.route('/routes/create', methods=['POST'])
def create_route_route():
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))
    actor_email = session.get('user_email', 'admin@empresa.com')

    success, message, _ = RouteService.create_route(
        company_db_name,
        request.form.get('number', ''),
        request.form.get('name', ''),
        request.form.get('zone', ''),
        actor_email,
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('personal_bp.routes_view'))

@personal_bp.route('/routes/<int:number>/assign-seller', methods=['POST'])
def assign_route_seller_route(number):
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))
    actor_email = session.get('user_email', 'admin@empresa.com')

    seller_email = request.form.get('seller_email', '').strip()
    if not seller_email:
        flash("Debe seleccionar un vendedor.", "danger")
        return redirect(url_for('personal_bp.routes_view'))

    db = get_company_db(company_db_name)
    seller = db['users'].find_one({"email": seller_email})
    if not seller:
        flash("Vendedor no encontrado.", "danger")
        return redirect(url_for('personal_bp.routes_view'))

    # Esta pantalla es, a propósito, el único lugar donde SÍ se permite
    # quitarle la ruta a un vendedor para dársela a otro — por eso no se
    # valida disponibilidad aquí como en el formulario general de Personal.
    db['users'].update_one({"_id": seller['_id']}, {"$set": {"route_number": number}})
    RouteService.sync_route_for_seller(company_db_name, number, seller_email, seller.get('name'), actor_email)
    flash(f"{seller.get('name')} asignado como titular de la ruta {number}.", 'success')
    return redirect(url_for('personal_bp.routes_view'))

@personal_bp.route('/api/delete/<string:user_id>', methods=['POST'])
def delete_employee_route(user_id):
    """Ruta para eliminar un registro de personal del MongoDB aislado."""
    company_db_name = session.get('company_db')
    if not company_db_name:
        return redirect(url_for('auth_bp.index'))

    try:
        db = get_company_db(company_db_name)
        users_col = db['users']
        
        query_id = ObjectId(user_id) if len(user_id) == 24 else user_id
        result = users_col.delete_one({"_id": query_id})
        
        if result.deleted_count > 0:
            flash("Personal eliminado correctamente.", "success")
        else:
            flash("No se encontró el registro a eliminar.", "warning")
            
    except Exception as e:
        print(f"Error al eliminar personal en MongoDB: {e}")
        flash("No se pudo eliminar el registro.", "danger")

    return redirect(url_for('personal_bp.personal_view'))