import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv('DATABASE_URL')

if not database_url:
    raise RuntimeError("DATABASE_URL no está configurada en el archivo .env")

client = MongoClient(database_url)

# Apuntamos exactamente a la base de datos de la empresa que se ve en tu Atlas
db_name = "gestion360_j123456789"
db = client.get_database(db_name)

print(f"Limpiando colecciones en la base de datos de la empresa: {db_name}")

# Vaciamos los productos y los movimientos comerciales de prueba
db['products'].delete_many({})
db['commercial_movements'].delete_many({})

print("¡Listo! La base de datos de la empresa ha quedado completamente limpia.")