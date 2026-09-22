import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv('DATABASE_URL')

# Solución automática por si viene como 'postgres://' en vez de 'postgresql://'
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URI = database_url
SQLALCHEMY_TRACK_MODIFICATIONS = False

MASTER_TOKEN = "GESTION360-MASTER-2026"

print("¡Configuración de Aiven PostgreSQL cargada correctamente!")