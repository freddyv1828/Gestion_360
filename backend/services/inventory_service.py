# backend/services/inventory_service.py
from datetime import datetime
from bson import ObjectId
from database import get_company_db

def get_warehouses_service(company_db_name):
    """Obtiene todos los almacenes de la empresa y calcula su stock total."""
    db = get_company_db(company_db_name)
    warehouses_col = db['warehouses']
    products_col = db['products']
    
    warehouses = list(warehouses_col.find({}))
    for wh in warehouses:
        wh['_id'] = str(wh['_id'])
        # Calcular stock total en este almacén sumando los productos asociados
        products_in_wh = list(products_col.find({"warehouse_id": wh['_id']}))
        total_stock = sum(float(p.get('stock', 0)) for p in products_in_wh)
        wh['total_stock'] = round(total_stock, 2)
        
        # Asegurar valor por defecto si no existe la propiedad de venta
        if 'is_available_for_sale' not in wh:
            wh['is_available_for_sale'] = True
            
    return warehouses

def create_warehouse_service(company_db_name, name, description, is_available_for_sale=True):
    """Crea un nuevo almacén indicando si su mercancía cuenta o no para la venta."""
    if not name or not name.strip():
        return False, "El nombre del almacén es obligatorio."
        
    db = get_company_db(company_db_name)
    warehouses_col = db['warehouses']
    
    if warehouses_col.find_one({"name": {"$regex": f"^{name.strip()}$", "$options": "i"}}):
        return False, "Ya existe un almacén con ese nombre."
        
    warehouse_data = {
        "name": name.strip(),
        "description": description.strip() if description else "",
        "is_available_for_sale": bool(is_available_for_sale),
        "created_at": datetime.utcnow()
    }
    
    warehouses_col.insert_one(warehouse_data)
    return True, "Almacén creado exitosamente."

def update_warehouse_service(company_db_name, warehouse_id, name, description, is_available_for_sale):
    """Modifica los datos de un almacén existente (nombre, descripción y disponibilidad comercial)."""
    db = get_company_db(company_db_name)
    warehouses_col = db['warehouses']
    
    try:
        query_id = ObjectId(warehouse_id)
    except Exception:
        return False, "ID de almacén inválido."
        
    warehouse = warehouses_col.find_one({"_id": query_id})
    if not warehouse:
        return False, "Almacén no encontrado."
        
    warehouses_col.update_one(
        {"_id": query_id},
        {
            "$set": {
                "name": name.strip(),
                "description": description.strip() if description else "",
                "is_available_for_sale": bool(is_available_for_sale),
                "updated_at": datetime.utcnow()
            }
        }
    )
    return True, "Almacén actualizado con éxito."

def delete_warehouse_service(company_db_name, warehouse_id):
    """Elimina un almacén validando estrictamente que no posea stock de productos asociado."""
    db = get_company_db(company_db_name)
    warehouses_col = db['warehouses']
    products_col = db['products']
    
    try:
        query_id = ObjectId(warehouse_id)
    except Exception:
        return False, "ID de almacén inválido."
        
    # Validar si hay productos registrados en este almacén con stock > 0
    products_in_wh = list(products_col.find({"warehouse_id": str(query_id)}))
    total_stock = sum(float(p.get('stock', 0)) for p in products_in_wh)
    
    if total_stock > 0:
        return False, f"No se puede eliminar el almacén porque contiene existencias activas (Stock total: {total_stock}). Transfiera o descargue la mercancía primero."
        
    result = warehouses_col.delete_one({"_id": query_id})
    if result.deleted_count > 0:
        return True, "Almacén eliminado correctamente."
    return False, "No se pudo eliminar el almacén."

def get_products_service(company_db_name):
    """Obtiene el catálogo de productos cruzando la información del almacén de pertenencia."""
    db = get_company_db(company_db_name)
    products_col = db['products']
    warehouses_col = db['warehouses']
    
    products = list(products_col.find({}))
    warehouses = {str(wh['_id']): wh for wh in warehouses_col.find({})}
    
    formatted_products = []
    for p in products:
        p['_id'] = str(p['_id'])
        wh_id = p.get('warehouse_id')
        warehouse = warehouses.get(wh_id, {})
        
        p['warehouse_name'] = warehouse.get('name', 'Almacén Desconocido')
        # La disponibilidad de venta se hereda directamente de la configuración del almacén
        p['is_available_for_sale'] = warehouse.get('is_available_for_sale', True)
        
        formatted_products.append(p)
        
    return formatted_products

def create_product_service(company_db_name, form_data, creator_email):
    """Registra un producto en el inventario con lote, fecha de vencimiento, stock mínimo y su respectiva auditoría."""
    name = form_data.get('name', '').strip()
    sku = form_data.get('sku', '').strip()
    category = form_data.get('category', '').strip()
    subcategory = form_data.get('subcategory', '').strip()
    warehouse_id = form_data.get('warehouse_id', '').strip()
    
    batch = form_data.get('batch', '').strip()
    expiration_date = form_data.get('expiration_date', '').strip()
    
    min_stock_raw = form_data.get('min_stock', '').strip()
    try:
        min_stock = float(min_stock_raw) if min_stock_raw else 0.0
    except ValueError:
        min_stock = 0.0

    try:
        price = float(form_data.get('price', 0))
        stock = float(form_data.get('stock', 0))
    except ValueError:
        return False, "El precio y el stock deben ser valores numéricos válidos."
        
    unit_type = form_data.get('unit_type', 'unit')
    
    if not name or not category or not warehouse_id:
        return False, "Nombre, categoría y almacén de destino son campos obligatorios."
        
    db = get_company_db(company_db_name)
    products_col = db['products']
    warehouses_col = db['warehouses']
    
    # Validar que el almacén exista
    try:
        if not warehouses_col.find_one({"_id": ObjectId(warehouse_id)}):
            return False, "El almacén seleccionado no existe."
    except Exception:
        return False, "Almacén inválido."
        
    # Generar SKU automático si viene vacío
    if not sku:
        sku = f"SKU-{abs(hash(name)) % 100000:05d}"
        
    product_data = {
        "name": name,
        "sku": sku,
        "category": category,
        "subcategory": subcategory,
        "warehouse_id": warehouse_id,
        "price": price,
        "stock": stock,
        "min_stock": min_stock,
        "unit_type": unit_type,
        "batch": batch if batch else "N/A",
        "expiration_date": expiration_date if expiration_date else None,
        "created_by": creator_email,
        "created_at": datetime.utcnow()
    }
    
    products_col.insert_one(product_data)
    return True, f"Producto '{name}' registrado con éxito en el inventario."

def update_product_service(company_db_name, product_id, form_data, modifier_email):
    """
    Modifica datos descriptivos del producto (Nombre, SKU, Subcategoría, Categoría, Stock Mínimo).
    NOTA: Por seguridad contable y de auditoría (Kardex), precios y unidades/stock 
    no se modifican directamente aquí; se gestionan mediante movimientos especiales y traslados.
    """
    db = get_company_db(company_db_name)
    products_col = db['products']
    
    try:
        query_id = ObjectId(product_id)
    except Exception:
        return False, "ID de producto inválido."
        
    product = products_col.find_one({"_id": query_id})
    if not product:
        return False, "Producto no encontrado."
        
    name = form_data.get('name', '').strip()
    sku = form_data.get('sku', '').strip()
    category = form_data.get('category', '').strip()
    subcategory = form_data.get('subcategory', '').strip()
    
    min_stock_raw = form_data.get('min_stock', '').strip()
    try:
        min_stock = float(min_stock_raw) if min_stock_raw else 0.0
    except ValueError:
        min_stock = float(product.get('min_stock', 0.0))
    
    if not name or not category:
        return False, "El nombre y la categoría son obligatorios."
        
    update_data = {
        "name": name,
        "sku": sku if sku else product.get('sku'),
        "category": category,
        "subcategory": subcategory,
        "min_stock": min_stock,
        "updated_by": modifier_email,
        "updated_at": datetime.utcnow()
    }
    
    products_col.update_one({"_id": query_id}, {"$set": update_data})
    return True, "Información del producto actualizada correctamente."

def delete_product_service(company_db_name, product_id):
    """Elimina un producto validando que su stock sea 0 para proteger el inventario."""
    db = get_company_db(company_db_name)
    products_col = db['products']
    
    try:
        query_id = ObjectId(product_id)
    except Exception:
        return False, "ID de producto inválido."
        
    product = products_col.find_one({"_id": query_id})
    if not product:
        return False, "Producto no encontrado."
        
    if float(product.get('stock', 0)) > 0:
        return False, f"No se puede eliminar el producto '{product.get('name')}' porque tiene existencias activas ({product.get('stock')} {product.get('unit_type')}). Debe dar salida o realizar un ajuste de inventario primero."
        
    products_col.delete_one({"_id": query_id})
    return True, "Producto eliminado exitosamente del catálogo."