from pymongo import MongoClient
import os
from config import DATABASE_URL, CENTRAL_DB_NAME, MARKETPLACE_DB_NAME

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada en las variables de entorno (.env).")

# Inicializar cliente oficial de PyMongo con parámetros robustos de TLS/SSL para evitar el corte de red
client = MongoClient(
    DATABASE_URL,
    tls=True,
    tlsAllowInvalidCertificates=True,  # Evita bloqueos de certificado local durante el apretón de manos
    connectTimeoutMS=60000,
    socketTimeoutMS=60000
)

# Base de datos central para licencias, empresas e índice global de usuarios
db = client.get_database(CENTRAL_DB_NAME)

def get_central_db():
    """Retorna la base de datos central de control SaaS (gestion360_central)."""
    return client.get_database(CENTRAL_DB_NAME)

def get_marketplace_db():
    """Retorna la base de datos pública del marketplace de clientes y catálogo Dropi."""
    return client.get_database(MARKETPLACE_DB_NAME)

def get_company_db(company_db_name):
    """
    Retorna la base de datos específica y aislada de la empresa cliente en MongoDB Atlas.
    Ej: company_db_name = 'gestion360_j123456789'
    """
    if not company_db_name:
        raise ValueError("No se ha especificado el identificador de la base de datos de la empresa.")
    return client.get_database(company_db_name)