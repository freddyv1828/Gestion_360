import os
from dotenv import load_dotenv

# Cargar variables desde el archivo .env ubicado en backend/ o en la raíz
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

# Configuración de Seguridad y Sesión
SECRET_KEY = os.getenv("SECRET_KEY", "gestion360_secret_key_super_segura_2026")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "gestion360_jwt_secret_key_super_segura_2026")
MASTER_TOKEN = os.getenv("MASTER_TOKEN", "GESTION360-MASTER-2026")

# Conexión Central a MongoDB Atlas
DATABASE_URL = os.getenv("DATABASE_URL")
CENTRAL_DB_NAME = os.getenv("CENTRAL_DB_NAME", "gestion360_central")
MARKETPLACE_DB_NAME = os.getenv("MARKETPLACE_DB_NAME", "gestion360_marketplace")

# Configuración de Cloudflare R2 (S3 compatible)
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "gestion360-storage")
R2_PUBLIC_DOMAIN = os.getenv(
    "R2_PUBLIC_DOMAIN",
    f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}" if R2_ENDPOINT_URL else ""
)

# Integración Dropi (Almacén Virtual / Dropshipping de Prueba)
DROPI_API_BASE_URL = os.getenv("DROPI_API_BASE_URL", "https://api.dropi.co")
DROPI_API_KEY = os.getenv("DROPI_API_KEY", "")