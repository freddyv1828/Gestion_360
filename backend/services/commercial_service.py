from datetime import datetime
from bson import ObjectId
from database import get_company_db

class CommercialService:
    
    @staticmethod
    def get_commercial_products(company_db_name, filters=None):
        """
        Retorna la lista de productos filtrada por nombre, SKU, categoría o marca
        para optimizar el rendimiento y el procesamiento de datos.
        """
        db = get_company_db(company_db_name)
        products_col = db['products']
        
        query = {}
        if filters:
            search = filters.get('search', '').strip()
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"sku": {"$regex": search, "$options": "i"}}
                ]
            
            category = filters.get('category', '').strip()
            if category:
                query["category"] = {"$regex": f"^{category}$", "$options": "i"}
                
            brand = filters.get('brand', '').strip()
            if brand:
                query["brand"] = {"$regex": f"^{brand}$", "$options": "i"}

        try:
            products = list(products_col.find(query).sort('name', 1))
            for prod in products:
                prod['_id'] = str(prod['_id'])
                prod.setdefault('cost', 0.0)
                prod.setdefault('price', 0.0)
                prod.setdefault('margin', 0.0)
                prod.setdefault('category', 'Sin Categoría')
                prod.setdefault('sku', 'N/D')
                prod.setdefault('unit_type', 'unit')
                prod.setdefault('brand', 'N/D')
            return products
        except Exception as e:
            print(f"Error obteniendo productos comerciales: {e}")
            return []

    @staticmethod
    def get_commercial_kpis(company_db_name):
        """
        Calcula los macro números financieros y métricas clave para la gerencia:
        Costo total, valor de venta total, utilidad proyectada, margen global y gastos.
        """
        db = get_company_db(company_db_name)
        products_col = db['products']
        expenses_col = db['expenses'] if 'expenses' in db.list_collection_names() else None
        
        try:
            products = list(products_col.find({}))
            total_cost = 0.0
            total_sales_value = 0.0
            total_stock_items = 0
            
            for p in products:
                stock = float(p.get('stock', 0))
                cost = float(p.get('cost', 0.0))
                price = float(p.get('price', 0.0))
                
                total_cost += stock * cost
                total_sales_value += stock * price
                total_stock_items += stock
            
            potential_profit = total_sales_value - total_cost
            global_margin = round((potential_profit / total_sales_value * 100), 2) if total_sales_value > 0 else 0.0
            
            total_expenses = 0.0
            if expenses_col:
                expenses = list(expenses_col.find({}))
                total_expenses = sum(float(e.get('amount', 0.0)) for e in expenses)

            return {
                "total_cost": round(total_cost, 2),
                "total_sales_value": round(total_sales_value, 2),
                "potential_profit": round(potential_profit, 2),
                "global_margin": global_margin,
                "total_stock_items": round(total_stock_items, 2),
                "total_expenses": round(total_expenses, 2)
            }
        except Exception as e:
            print(f"Error calculando KPIs gerenciales: {e}")
            return {
                "total_cost": 0.0,
                "total_sales_value": 0.0,
                "potential_profit": 0.0,
                "global_margin": 0.0,
                "total_stock_items": 0.0,
                "total_expenses": 0.0
            }

    @staticmethod
    def get_active_warehouses(company_db_name):
        """
        Obtiene la lista de almacenes activos de la empresa para los selectores.
        """
        db = get_company_db(company_db_name)
        warehouses_col = db['warehouses']
        
        try:
            warehouses = list(warehouses_col.find({}).sort('name', 1))
            for w in warehouses:
                w['_id'] = str(w['_id'])
            
            if not warehouses:
                return [{"name": "Almacén Principal"}, {"name": "Cuarentena"}, {"name": "Depósito Secundario"}]
                
            return warehouses
        except Exception as e:
            print(f"Error obteniendo almacenes: {e}")
            return [{"name": "Almacén Principal"}, {"name": "Cuarentena"}]

    @staticmethod
    def create_commercial_product(company_db_name, form_data, creator_email):
        name = form_data.get('name', '').strip()
        sku = form_data.get('sku', '').strip()
        category = form_data.get('category', '').strip()
        brand = form_data.get('brand', '').strip()
        unit_type = form_data.get('unit_type', 'unit')
        
        try:
            cost = float(form_data.get('cost', 0.0))
            price = float(form_data.get('price', 0.0))
        except ValueError:
            return False, "El costo y el precio deben ser valores numéricos válidos."
            
        if not name or not category:
            return False, "El nombre y la categoría son campos obligatorios."
            
        db = get_company_db(company_db_name)
        products_col = db['products']
        
        if sku and products_col.find_one({"sku": {"$regex": f"^{sku}$", "$options": "i"}}):
            return False, f"El SKU '{sku}' ya se encuentra registrado en el maestro."
            
        if not sku:
            sku = f"COM-{abs(hash(name)) % 100000:05d}"
            
        margin = 0.0
        if price > 0:
            margin = round(((price - cost) / price) * 100, 2)
            
        product_doc = {
            "name": name,
            "sku": sku,
            "category": category,
            "brand": brand if brand else "N/D",
            "unit_type": unit_type,
            "cost": cost,
            "price": price,
            "margin": margin,
            "created_by": creator_email,
            "created_at": datetime.utcnow()
        }
        
        try:
            products_col.insert_one(product_doc)
            return True, f"Producto '{name}' creado exitosamente en el maestro comercial."
        except Exception as e:
            return False, f"Error al registrar el producto: {str(e)}"

    @staticmethod
    def register_auditable_movement(company_db_name, form_data, user_email):
        product_id = form_data.get('product_id', '').strip()
        source_warehouse = form_data.get('source_warehouse', '').strip()
        dest_warehouse = form_data.get('dest_warehouse', '').strip()
        movement_type = form_data.get('movement_type', 'TRASLADO')
        reason = form_data.get('reason', '').strip()
        
        try:
            quantity = float(form_data.get('quantity', 0))
        except ValueError:
            return False, "La cantidad debe ser un valor numérico válido."
            
        if not product_id or quantity <= 0:
            return False, "Debe seleccionar un producto y especificar una cantidad mayor a cero."
            
        db = get_company_db(company_db_name)
        movements_col = db['inventory_movements']
        
        try:
            query_id = ObjectId(product_id)
        except Exception:
            return False, "ID de producto inválido."
            
        movement_doc = {
            "product_id": str(query_id),
            "source_warehouse": source_warehouse,
            "dest_warehouse": dest_warehouse,
            "quantity": quantity,
            "movement_type": movement_type,
            "reason": reason if reason else "Sin motivo especificado",
            "user": user_email,
            "timestamp": datetime.utcnow()
        }
        
        try:
            movements_col.insert_one(movement_doc)
            return True, "Movimiento auditable registrado correctamente."
        except Exception as e:
            return False, f"Error registrando auditoría: {str(e)}"