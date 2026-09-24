import os
from dotenv import load_dotenv

load_dotenv()

# Ya no dependemos de SQLAlchemy, dejamos el token y configuraciones base
MASTER_TOKEN = "GESTION360-MASTER-2026"

print("¡Configuración de variables cargada correctamente!")