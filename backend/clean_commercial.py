import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv('DATABASE_URL')

if not database_url:
    raise RuntimeError("DATABASE_URL no está configurada en el archivo .env")

client = MongoClient(database_url)

# Reemplaza 'gestion360_j123456789' o el nombre exacto de la base de datos de tu empresa de prueba
# O puedes listar las bases de datos de clientes si prefieres limpiar todas.
db_name = "gestion360" # O el nombre de la BD comercial de la empresa
db = client.get_database(db_name)

print(f"Limpiando colecciones comerciales en la base de datos: {db_name}")

# Limpiar colecciones de productos y movimientos comerciales
db['products'].delete_many({})
db['commercial_movements'].delete_many({})

print("¡Colecciones limpiadas con éxito! Ya puedes empezar a registrar productos desde cero con el nuevo flujo de almacenes.")