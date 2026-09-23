import os
import re
import base64
import unicodedata
import boto3
from botocore.config import Config
import sqlalchemy

# Configuración de Cloudflare R2 (S3 compatible) con tus credenciales reales
R2_ENDPOINT_URL = "https://f6142b0b6187db4eda007cc0962ac8a4.r2.cloudflarestorage.com"
R2_ACCESS_KEY_ID = "50613beb9e89af5c41f2d07ee23c11ac"
R2_SECRET_ACCESS_KEY = "feca9e0e7fd65ac91c518e6e6b680516d5ad57df1dfedf30f686a17be9d7824a"
R2_BUCKET_NAME = "gestion360-storage"
R2_PUBLIC_DOMAIN = "https://f6142b0b6187db4eda007cc0962ac8a4.r2.cloudflarestorage.com/gestion360-storage"

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def register_business_logic(data):
    try:
        from config import SQLALCHEMY_DATABASE_URI, MASTER_TOKEN

        engine = sqlalchemy.create_engine(SQLALCHEMY_DATABASE_URI)
        connection = engine.connect()
        metadata = sqlalchemy.MetaData()

        # Tabla de empresas con columnas para las URLs de los documentos en R2
        businesses_table = sqlalchemy.Table(
            'businesses',
            metadata,
            sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True, autoincrement=True),
            sqlalchemy.Column('name', sqlalchemy.String(150), nullable=False),
            sqlalchemy.Column('rif', sqlalchemy.String(20), unique=True, nullable=False),
            sqlalchemy.Column('tax_right', sqlalchemy.String(100)),
            sqlalchemy.Column('commercial_direction', sqlalchemy.Text),
            sqlalchemy.Column('owner_email', sqlalchemy.String(120)),
            sqlalchemy.Column('plan_type', sqlalchemy.String(50), default='free'),
            sqlalchemy.Column('rif_file_url', sqlalchemy.Text),
            sqlalchemy.Column('acta_file_url', sqlalchemy.Text),
            sqlalchemy.Column('mercantil_file_url', sqlalchemy.Text)
        )

        tokens_table = sqlalchemy.Table('activation_tokens', metadata, autoload_with=engine)
        metadata.create_all(engine)

        activation_token = data.get("activationToken", "").strip()
        name = data.get("name", "").strip()
        rif = data.get("rif", "").strip()
        owner_email = data.get("ownerEmail", "").strip()

        rif_regex = r"^[VEJPG]-[0-9]{8}-[0-9]$"
        if not re.match(rif_regex, rif):
            connection.close()
            return {"error": "Formato de RIF inválido."}, 400

        # Validar token
        if activation_token != MASTER_TOKEN:
            token_select = sqlalchemy.select(tokens_table).where(tokens_table.c.token_value == activation_token)
            token_record = connection.execute(token_select).fetchone()

            if not token_record or token_record._asdict().get("is_used", False):
                connection.close()
                return {"error": "Token de activación inválido o ya utilizado."}, 403

        # Verificar si ya existe el RIF
        select_stmt = sqlalchemy.select(businesses_table).where(businesses_table.c.rif == rif)
        if connection.execute(select_stmt).fetchone():
            connection.close()
            return {"error": "Ya existe una empresa registrada con este RIF."}, 400

        # --- SUBIDA DE ARCHIVOS A CLOUDFLARE R2 ORDENADOS POR RIF ---
        s3 = get_r2_client()
        documents = data.get("documents", {})
        saved_file_urls = {}

        doc_keys_map = {
            "rifFile": "rif_file_url",
            "actaFile": "acta_file_url",
            "mercantilFile": "mercantil_file_url"
        }

        for client_key, db_column in doc_keys_map.items():
            doc_info = documents.get(client_key)
            if doc_info and "base64" in doc_info and "filename" in doc_info:
                file_name = doc_info["filename"]
                
                # Normalizar nombre del archivo
                normalized_filename = unicodedata.normalize('NFKD', file_name).encode('ASCII', 'ignore').decode('ASCII')
                normalized_filename = re.sub(r'[^\w\-_\.]', '_', normalized_filename)
                
                # Estructura de carpeta basada en el RIF de la empresa
                object_key = f"companies/{rif}/{normalized_filename}"

                try:
                    base64_data = doc_info["base64"]
                    if "," in base64_data:
                        base64_data = base64_data.split(",")[1]

                    file_bytes = base64.b64decode(base64_data)
                    
                    # Subir directamente los bytes a Cloudflare R2 en la carpeta del RIF
                    s3.put_object(
                        Bucket=R2_BUCKET_NAME,
                        Key=object_key,
                        Body=file_bytes,
                        ContentType="application/pdf"
                    )
                    
                    # Generar la URL de acceso pública
                    file_url = f"{R2_PUBLIC_DOMAIN}/{object_key}"
                    saved_file_urls[db_column] = file_url
                except Exception as file_err:
                    print(f"Error subiendo {client_key} a R2: {file_err}")
                    saved_file_urls[db_column] = None
            else:
                saved_file_urls[db_column] = None

        # Insertar registro en Aiven PostgreSQL
        insert_stmt = businesses_table.insert().values(
            name=name,
            rif=rif,
            tax_right=data.get("taxRight", "").strip(),
            commercial_direction=data.get("commercialDirection", "").strip(),
            owner_email=owner_email,
            plan_type=data.get("planType", "free"),
            rif_file_url=saved_file_urls.get("rif_file_url"),
            acta_file_url=saved_file_urls.get("acta_file_url"),
            mercantil_file_url=saved_file_urls.get("mercantil_file_url")
        )
        connection.execute(insert_stmt)

        # Quemar token si no es master
        if activation_token != MASTER_TOKEN:
            update_token_stmt = (
                tokens_table.update()
                .where(tokens_table.c.token_value == activation_token)
                .values(is_used=True, used_at=sqlalchemy.func.now())
            )
            connection.execute(update_token_stmt)

        connection.commit()
        connection.close()

        return {
            "success": True,
            "message": "Empresa registrada, documentos organizados por RIF en Cloudflare R2 y datos guardados exitosamente.",
        }, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error en el servidor: {str(e)}"}, 500