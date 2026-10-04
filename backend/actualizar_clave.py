from werkzeug.security import generate_password_hash
from database import client

nueva_password = "mi_nueva_password_123"
nuevo_hash = generate_password_hash(nueva_password)

# 1. Crear y poblar la base de datos CENTRAL ('gestion360_central') que tu código busca
central_db = client.get_database("gestion360_central")

# Registrar la empresa en la colección 'businesses' que exige tu login_service.py
central_db["businesses"].update_one(
    {"rif": "J-12345678-9"},
    {
        "$set": {
            "id": 1,
            "name": "Empresa Principal C.A.",
            "rif": "J-12345678-9",
            "database_name": "gestion360_j123456789",
            "status": "active"
        }
    },
    upsert=True
)

# 2. Asegurar que el usuario administrador exista también en la BD del tenant ('gestion360_j123456789')
tenant_db = client.get_database("gestion360_j123456789")
tenant_db["users"].update_one(
    {"email": "freddy.valero88@gmail.com"},
    {
        "$set": {
            "password": nuevo_hash,
            "name": "freddy valero",
            "role": "admin",
            "business_id": 1,
            "rif": "J-12345678-9"
        }
    },
    upsert=True
)

print("¡Base central y tenant sincronizadas correctamente en MongoDB Atlas!")