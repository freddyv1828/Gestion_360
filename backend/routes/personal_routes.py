from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
from io import BytesIO
import sqlalchemy
from utils import get_r2_client, get_db_connection, R2_BUCKET_NAME
from services.personal_service import update_employee_service, create_employee_service

personal_bp = Blueprint('personal_bp', __name__, url_prefix='/personal')

@personal_bp.route('/', methods=['GET'])
def personal_view():
    """Vista principal de gestión de personal."""
    company_name = session.get('company_name', 'Mi Empresa')
    company_rif = session.get('company_rif', 'J-00000000-0')
    
    staff_members = []
    try:
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        users_table = sqlalchemy.Table('users', metadata, autoload_with=engine)
        
        with engine.connect() as connection:
            stmt = sqlalchemy.select(users_table)
            result = connection.execute(stmt).fetchall()
            staff_members = [dict(row._mapping) for row in result]
            
    except Exception as e:
        print(f"Error cargando personal: {e}")

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
    """Ruta para registrar nuevo personal."""
    creator_email = session.get('user_email', 'admin@empresa.com')
    company_rif = session.get('company_rif', 'J-12345678-9')

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

@personal_bp.route('/api/update/<int:user_id>', methods=['POST'])
def update_employee_route(user_id):
    """Ruta para modificar personal existente."""
    modifier_email = session.get('user_email', 'admin@empresa.com')
    company_rif = session.get('company_rif', 'J-12345678-9')

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

@personal_bp.route('/api/delete/<int:user_id>', methods=['POST'])
def delete_employee_route(user_id):
    """Ruta para eliminar un registro de personal de la BD."""
    try:
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        users_table = sqlalchemy.Table('users', metadata, autoload_with=engine)

        with engine.connect() as connection:
            delete_stmt = users_table.delete().where(users_table.c.id == user_id)
            connection.execute(delete_stmt)
            connection.commit()
            flash("Personal eliminado correctamente.", "success")
    except Exception as e:
        print(f"Error al eliminar personal: {e}")
        flash("No se pudo eliminar el registro.", "danger")

    return redirect(url_for('personal_bp.personal_view'))