from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_marketplace_db, get_company_db
from services.login_service import generate_jwt_token


class MarketplaceService:

    @staticmethod
    def get_public_catalog(limit=200):
        """Vitrina pública (sin autenticación) del catálogo Dropi para Guest Browsing."""
        db = get_marketplace_db()
        items = list(db['dropi_catalog'].find({}).limit(limit))
        for i in items:
            i['_id'] = str(i['_id'])
        return items

    @staticmethod
    def get_company_inventory_for_seller(company_db_name, limit=500):
        """Inventario de la empresa para descarga en la app del vendedor corporativo."""
        if not company_db_name:
            return []
        db = get_company_db(company_db_name)
        products = list(db['products'].find({"is_active": {"$ne": False}}).limit(limit))
        for p in products:
            p['_id'] = str(p['_id'])
        return products

    @staticmethod
    def checkout(form_data):
        """
        Registra el pedido de un cliente de la vitrina móvil, con registro/login
        en caliente si el correo no tiene cuenta todavía.
        Retorna (ok, mensaje, payload_o_None).
        """
        email = (form_data.get('email') or '').strip().lower()
        password = (form_data.get('password') or '').strip()
        name = (form_data.get('name') or '').strip()
        items = form_data.get('items') or []

        if not email:
            return False, "El correo electrónico es obligatorio.", None
        if not items:
            return False, "El carrito no puede estar vacío.", None

        db = get_marketplace_db()
        clients_col = db['clients']
        client = clients_col.find_one({"email": email})

        if client:
            if not password or not check_password_hash(client.get('password', ''), password):
                return False, "Credenciales inválidas para una cuenta ya existente con este correo.", None
        else:
            if not password:
                return False, "Debe definir una contraseña para registrar su cuenta.", None
            new_client = {
                "email": email,
                "name": name or email.split('@')[0],
                "password": generate_password_hash(password),
                "created_at": datetime.utcnow()
            }
            inserted = clients_col.insert_one(new_client)
            client = new_client
            client['_id'] = inserted.inserted_id

        try:
            total = sum(float(item.get('price', 0)) * float(item.get('qty', 1)) for item in items)
        except (TypeError, ValueError, AttributeError):
            return False, "Los artículos del carrito contienen datos inválidos.", None

        order_doc = {
            "client_id": client['_id'],
            "client_email": email,
            "items": items,
            "total": total,
            "status": "pendiente",
            "created_at": datetime.utcnow()
        }
        order_result = db['client_orders'].insert_one(order_doc)

        token = generate_jwt_token({
            "email": email,
            "name": client.get('name'),
            "user_type": "app_client"
        })

        return True, "Pedido registrado con éxito.", {
            "order_id": str(order_result.inserted_id),
            "total": total,
            "token": token,
            "client": {"email": email, "name": client.get('name')}
        }
