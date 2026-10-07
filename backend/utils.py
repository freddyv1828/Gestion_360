# backend/utils.py
from datetime import datetime
import boto3
from bson import ObjectId
from botocore.config import Config
from config import (
    R2_ENDPOINT_URL,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_PUBLIC_DOMAIN,
)


def json_safe(value):
    """
    Convierte recursivamente un documento (o lista de documentos) de MongoDB a
    tipos nativos serializables por json/jsonify: ObjectId -> str, datetime ->
    ISO 8601. Usar SIEMPRE antes de devolver un documento Mongo crudo (con
    subestructuras como items[], client_id, created_at) en un endpoint JSON —
    jsonify() no sabe serializar ObjectId ni datetime y revienta con un 500.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value

def get_r2_client():
    """Retorna un cliente boto3 configurado para Cloudflare R2 sin exponer credenciales."""
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )