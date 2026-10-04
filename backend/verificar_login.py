from werkzeug.security import check_password_hash
from database import client
db = client['gestion360_j123456789']
user = db['users'].find_one({"email": "freddy.valero88@gmail.com"})

if user:
    print("Usuario encontrado en Atlas.")
    print("Hash almacenado:", user['password'])
    # Probemos si valida con la nueva clave
    valido = check_password_hash(user['password'], "mi_nueva_password_123")
    print("¿La contraseña 'mi_nueva_password_123' es válida?:", valido)
else:
    print("No se encontró el usuario.")