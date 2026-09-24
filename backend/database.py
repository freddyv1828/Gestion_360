from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# La URL de conexión a tu clúster de MongoDB Atlas
database_url = os.getenv('DATABASE_URL')

# Inicializar cliente oficial de PyMongo (Se conecta una sola vez al clúster)
client = MongoClient(database_url)

# (Opcional) Base de datos por defecto o master si se requiere en algún proceso general
db = client.get_database('gestion360')

def get_company_db(company_db_name):
    """
    Retorna la base de datos específica y aislada de la empresa cliente en MongoDB Atlas.
    Ej: company_db_name = 'gestion360_j123456789'
    """
    if not company_db_name:
        raise ValueError("No se ha especificado el nombre de la base de datos de la empresa en la sesión.")
    return client.get_database(company_db_name)