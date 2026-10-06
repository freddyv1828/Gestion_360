from datetime import datetime
from bson import ObjectId
from database import get_company_db

DISCOUNT_TYPES = {'percentage', 'fixed'}


class CouponService:

    @staticmethod
    def get_active_coupons(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        coupons = list(db['coupons'].find({"is_active": {"$ne": False}}).sort('code', 1))
        for c in coupons:
            c['_id'] = str(c['_id'])
        return coupons

    @staticmethod
    def create_coupon(company_db_name, form_data, creator_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        code = (form_data.get('code') or '').strip().upper()
        discount_type = (form_data.get('discount_type') or 'percentage').strip()
        expires_at_raw = (form_data.get('expires_at') or '').strip()

        if not code:
            return False, "El código del cupón es obligatorio."
        if discount_type not in DISCOUNT_TYPES:
            return False, "Tipo de descuento no válido."

        try:
            discount_value = float(form_data.get('discount_value', 0) or 0)
        except ValueError:
            return False, "El valor del descuento debe ser numérico."
        if discount_value <= 0:
            return False, "El valor del descuento debe ser mayor a cero."
        if discount_type == 'percentage' and discount_value > 100:
            return False, "Un descuento porcentual no puede superar 100%."

        try:
            usage_limit = int(form_data.get('usage_limit', 0) or 0)
        except ValueError:
            usage_limit = 0

        if db['coupons'].find_one({"code": code}):
            return False, f"Ya existe un cupón con el código '{code}'."

        expires_at = None
        if expires_at_raw:
            try:
                expires_at = datetime.strptime(expires_at_raw, '%Y-%m-%d')
            except ValueError:
                expires_at = None

        db['coupons'].insert_one({
            "code": code,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "usage_limit": usage_limit,
            "times_used": 0,
            "expires_at": expires_at,
            "is_active": True,
            "created_by": creator_email,
            "created_at": datetime.utcnow()
        })
        return True, f"Cupón '{code}' creado con éxito."

    @staticmethod
    def validate_coupon(company_db_name, code):
        """Retorna (ok, mensaje_o_None, coupon_doc_o_None) sin consumirlo todavía."""
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", None

        code = (code or '').strip().upper()
        if not code:
            return False, "Código de cupón vacío.", None

        coupon = db['coupons'].find_one({"code": code, "is_active": {"$ne": False}})
        if not coupon:
            return False, f"El cupón '{code}' no existe o está inactivo.", None

        if coupon.get('expires_at') and coupon['expires_at'] < datetime.utcnow():
            return False, f"El cupón '{code}' ya expiró.", None

        usage_limit = coupon.get('usage_limit', 0)
        if usage_limit and coupon.get('times_used', 0) >= usage_limit:
            return False, f"El cupón '{code}' alcanzó su límite de usos.", None

        return True, None, coupon

    @staticmethod
    def redeem_coupon(company_db_name, coupon_id):
        db = get_company_db(company_db_name)
        if db is None:
            return
        db['coupons'].update_one({"_id": ObjectId(coupon_id)}, {"$inc": {"times_used": 1}})

    @staticmethod
    def deactivate_coupon(company_db_name, coupon_id):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        result = db['coupons'].update_one({"_id": ObjectId(coupon_id)}, {"$set": {"is_active": False}})
        if result.modified_count > 0:
            return True, "Cupón desactivado."
        return False, "Cupón no encontrado."
