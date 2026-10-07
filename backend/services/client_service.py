from datetime import datetime
from bson import ObjectId
from database import get_company_db
from utils import json_safe

CLIENT_TYPES = {'fiscal', 'natural'}


class ClientService:

    @staticmethod
    def get_paginated_clients(company_db_name, filters=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        clients_col = db['clients']
        query = {"is_active": {"$ne": False}}

        if filters:
            search = (filters.get('search') or '').strip()
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"rif_cedula": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}}
                ]

            client_type = (filters.get('client_type') or '').strip()
            if client_type in CLIENT_TYPES:
                query["client_type"] = client_type

            credit_min = (filters.get('credit_min') or '').strip()
            credit_max = (filters.get('credit_max') or '').strip()
            if credit_min or credit_max:
                credit_query = {}
                if credit_min:
                    try:
                        credit_query["$gte"] = float(credit_min)
                    except ValueError:
                        pass
                if credit_max:
                    try:
                        credit_query["$lte"] = float(credit_max)
                    except ValueError:
                        pass
                if credit_query:
                    query["credit_limit"] = credit_query

        skip = (page - 1) * per_page
        cursor = clients_col.find(query).sort('name', 1).skip(skip).limit(per_page)
        clients = list(cursor)
        for c in clients:
            c.setdefault('client_type', 'fiscal')
            c.setdefault('credit_limit', 0.0)
            c.setdefault('phone', '')
            c.setdefault('address', '')

        total_count = clients_col.count_documents(query)
        return json_safe(clients), total_count

    @staticmethod
    def count_active_clients(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return 0
        return db['clients'].count_documents({"is_active": {"$ne": False}})

    @staticmethod
    def get_client(company_db_name, client_id):
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            client = db['clients'].find_one({"_id": ObjectId(client_id)})
        except Exception:
            return None
        return json_safe(client) if client else None

    @staticmethod
    def create_or_update_client(company_db_name, form_data, creator_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        clients_col = db['clients']
        client_id = (form_data.get('client_id') or '').strip()

        name = (form_data.get('name') or '').strip()
        rif_cedula = (form_data.get('rif_cedula') or '').strip()
        client_type = (form_data.get('client_type') or 'fiscal').strip()
        email = (form_data.get('email') or '').strip()
        phone = (form_data.get('phone') or '').strip()
        address = (form_data.get('address') or '').strip()

        if not name:
            return False, "El nombre o razón social del cliente es obligatorio."
        if not rif_cedula:
            return False, "El RIF o cédula del cliente es obligatorio."
        if client_type not in CLIENT_TYPES:
            client_type = 'fiscal'

        try:
            credit_limit = float(form_data.get('credit_limit', 0) or 0)
        except ValueError:
            return False, "El límite de crédito debe ser numérico."

        existing = clients_col.find_one({
            "rif_cedula": rif_cedula,
            **({"_id": {"$ne": ObjectId(client_id)}} if client_id else {})
        })
        if existing:
            return False, f"Ya existe un cliente registrado con el RIF/Cédula {rif_cedula}."

        try:
            if client_id:
                clients_col.update_one(
                    {"_id": ObjectId(client_id)},
                    {"$set": {
                        "name": name,
                        "rif_cedula": rif_cedula,
                        "client_type": client_type,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "credit_limit": credit_limit,
                        "updated_at": datetime.utcnow()
                    }}
                )
                return True, f"Cliente '{name}' actualizado con éxito."
            else:
                clients_col.insert_one({
                    "name": name,
                    "rif_cedula": rif_cedula,
                    "client_type": client_type,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "credit_limit": credit_limit,
                    "is_active": True,
                    "created_by": creator_email,
                    "created_at": datetime.utcnow()
                })
                return True, f"Cliente '{name}' registrado con éxito."
        except Exception as e:
            return False, f"Error al guardar el cliente: {str(e)}"

    @staticmethod
    def soft_delete_client(company_db_name, client_id):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            result = db['clients'].update_one(
                {"_id": ObjectId(client_id)},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            if result.modified_count > 0:
                return True, "Cliente inactivado correctamente."
            return False, "Cliente no encontrado."
        except Exception as e:
            return False, f"Error al inactivar: {str(e)}"
