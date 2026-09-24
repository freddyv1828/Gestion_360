# backend/routes/personal_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
from io import BytesIO
from bson import ObjectId
from database import get_company_db
from utils import get_r2_client, R2_BUCKET_NAME
from services.personal_service import update_employee_service, create_employee_service

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