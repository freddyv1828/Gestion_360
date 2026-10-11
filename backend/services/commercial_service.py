from datetime import datetime
from bson import ObjectId
import os
import unicodedata
import re
from database import get_company_db
from utils import get_r2_client, R2_BUCKET_NAME, R2_PUBLIC_DOMAIN

DEMO_PRODUCTS = [
    {"name": "Queso Blanco Duro 1kg", "sku": "QBD-1KG", "category": "Quesos", "cost": 4.20, "price": 7.50, "unit_type": "kg", "stock": 150, "weight_kg": 1.0},
    {"name": "Queso Blanco Semiduro 1kg", "sku": "QBS-1KG", "category": "Quesos", "cost": 3.80, "price": 6.80, "unit_type": "kg", "stock": 150, "weight_kg": 1.0},
    {"name": "Queso Guayanés 1kg", "sku": "QGY-1KG", "category": "Quesos", "cost": 4.50, "price": 8.00, "unit_type": "kg", "stock": 100, "weight_kg": 1.0},
    {"name": "Queso de Mano 500g", "sku": "QMN-500G", "category": "Quesos", "cost": 2.60, "price": 4.80, "unit_type": "kg", "stock": 120, "weight_kg": 0.5},
    {"name": "Queso Crema 250g", "sku": "QCR-250G", "category": "Quesos", "cost": 1.50, "price": 2.90, "unit_type": "unidad", "stock": 200, "weight_kg": 0.25},
    {"name": "Queso Ricota 500g", "sku": "QRC-500G", "category": "Quesos", "cost": 2.00, "price": 3.70, "unit_type": "unidad", "stock": 100, "weight_kg": 0.5},
    {"name": "Leche Entera Pasteurizada 1L", "sku": "LEP-1L", "category": "Leche", "cost": 0.90, "price": 1.60, "unit_type": "litros", "stock": 300, "weight_kg": 1.03},
    {"name": "Leche Semidescremada 1L", "sku": "LSD-1L", "category": "Leche", "cost": 0.88, "price": 1.55, "unit_type": "litros", "stock": 250, "weight_kg": 1.03},
    {"name": "Leche en Polvo Completa 900g", "sku": "LPC-900G", "category": "Leche", "cost": 5.20, "price": 8.90, "unit_type": "unidad", "stock": 80, "weight_kg": 0.9},
    {"name": "Yogurt Natural 1L", "sku": "YGN-1L", "category": "Yogurt", "cost": 1.40, "price": 2.50, "unit_type": "litros", "stock": 150, "weight_kg": 1.03},
    {"name": "Yogurt Fresa 1L", "sku": "YGF-1L", "category": "Yogurt", "cost": 1.45, "price": 2.60, "unit_type": "litros", "stock": 150, "weight_kg": 1.03},
    {"name": "Yogurt Bebible 200ml", "sku": "YGB-200ML", "category": "Yogurt", "cost": 0.35, "price": 0.70, "unit_type": "unidad", "stock": 400, "weight_kg": 0.2},
    {"name": "Mantequilla con Sal 250g", "sku": "MTS-250G", "category": "Mantequilla", "cost": 1.80, "price": 3.20, "unit_type": "unidad", "stock": 120, "weight_kg": 0.25},
    {"name": "Mantequilla sin Sal 250g", "sku": "MTN-250G", "category": "Mantequilla", "cost": 1.80, "price": 3.20, "unit_type": "unidad", "stock": 100, "weight_kg": 0.25},
    {"name": "Nata / Crema de Leche 500ml", "sku": "NTA-500ML", "category": "Otros Lácteos", "cost": 1.60, "price": 2.90, "unit_type": "unidad", "stock": 90, "weight_kg": 0.52},
    {"name": "Suero Costeño 1L", "sku": "SRC-1L", "category": "Otros Lácteos", "cost": 1.00, "price": 1.80, "unit_type": "litros", "stock": 100, "weight_kg": 1.0},
    {"name": "Dulce de Leche 400g", "sku": "DDL-400G", "category": "Otros Lácteos", "cost": 1.90, "price": 3.40, "unit_type": "unidad", "stock": 70, "weight_kg": 0.4},
    {"name": "Queso Parmesano Rallado 200g", "sku": "QPR-200G", "category": "Quesos", "cost": 2.80, "price": 5.20, "unit_type": "unidad", "stock": 60, "weight_kg": 0.2},
]


def _add_stock_batch(batches, warehouse_id, quantity, batch_code=None, exp_date=None):
    """Suma stock a un lote existente (mismo código + almacén) o crea uno nuevo. Retorna el batch_code usado."""
    batch_code = (batch_code or f"AUTO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}").strip()
    for b in batches:
        if b.get('warehouse_id') == warehouse_id and b.get('batch_code') == batch_code:
            b['qty'] = float(b.get('qty', 0.0)) + quantity
            if exp_date:
                b['exp_date'] = exp_date
            return batch_code
    batches.append({
        "batch_code": batch_code,
        "exp_date": exp_date or None,
        "qty": quantity,
        "warehouse_id": warehouse_id
    })
    return batch_code


def _consume_stock_batches(batches, warehouse_id, quantity, batch_code=None):
    """
    Consume stock de los lotes de un almacén bajo criterio FEFO (First-Expired-First-Out).
    Si se especifica batch_code, consume exclusivamente de ese lote.
    Retorna (ok, error_msg, consumed_detail).
    """
    candidates = [b for b in batches if b.get('warehouse_id') == warehouse_id and float(b.get('qty', 0.0)) > 0]
    if batch_code:
        candidates = [b for b in candidates if b.get('batch_code') == batch_code]

    candidates.sort(key=lambda b: (b.get('exp_date') is None, b.get('exp_date') or ''))

    available = sum(float(b.get('qty', 0.0)) for b in candidates)
    if available < quantity:
        return False, f"Stock insuficiente en el almacén/lote seleccionado (Disponible: {available}).", []

    remaining = quantity
    consumed = []
    for b in candidates:
        if remaining <= 0:
            break
        take = min(float(b.get('qty', 0.0)), remaining)
        b['qty'] = float(b.get('qty', 0.0)) - take
        remaining -= take
        consumed.append({"batch_code": b.get('batch_code'), "exp_date": b.get('exp_date'), "qty": take})

    batches[:] = [b for b in batches if float(b.get('qty', 0.0)) > 0.0001]
    return True, None, consumed


def _recompute_stock_by_warehouse(batches):
    stock_by_wh = {}
    for b in batches:
        wh = b.get('warehouse_id')
        if not wh:
            continue
        stock_by_wh[wh] = stock_by_wh.get(wh, 0.0) + float(b.get('qty', 0.0))
    return stock_by_wh


def get_available_quantity(product, warehouse_id):
    """
    Existencia física menos lo reservado por pedidos pendientes de facturar en ese
    almacén. Esto es lo que debe validarse al crear un Pedido (nunca el stock bruto),
    para que dos pedidos simultáneos no puedan vender la misma mercancía dos veces.
    """
    stock_by_wh = product.get('stock_by_warehouse', {}) or {}
    reserved_by_wh = product.get('reserved_by_warehouse', {}) or {}
    physical = float(stock_by_wh.get(warehouse_id, stock_by_wh.get(str(warehouse_id), 0.0)))
    reserved = float(reserved_by_wh.get(warehouse_id, reserved_by_wh.get(str(warehouse_id), 0.0)))
    return physical - reserved


def _reserve_quantity(reserved_by_wh, warehouse_id, quantity):
    reserved_by_wh[warehouse_id] = float(reserved_by_wh.get(warehouse_id, 0.0)) + quantity


def _release_quantity(reserved_by_wh, warehouse_id, quantity):
    current = float(reserved_by_wh.get(warehouse_id, 0.0))
    new_value = max(0.0, current - quantity)
    if new_value <= 0.0001:
        reserved_by_wh.pop(warehouse_id, None)
    else:
        reserved_by_wh[warehouse_id] = new_value


class CommercialService:

    MOVEMENT_ALIASES = {
        'in': 'ENTRADA', 'out': 'SALIDA', 'transfer': 'TRASLADO',
        'ENTRADA': 'ENTRADA', 'SALIDA': 'SALIDA', 'TRASLADO': 'TRASLADO',
        'CARGO': 'CARGO', 'DESCARGO': 'DESCARGO',
    }
    MOVEMENTS_REQUIRING_ACTA = {'CARGO', 'DESCARGO'}

    @staticmethod
    def get_warehouses(company_db_name):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        
        wh_col = db['warehouses']
        warehouses = list(wh_col.find({"is_active": {"$ne": False}}))
            
        for wh in warehouses:
            wh['_id'] = str(wh['_id'])
        return warehouses

    @staticmethod
    def create_warehouse(company_db_name, form_data):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
            
        wh_col = db['warehouses']
        name = form_data.get('name', '').strip()
        code = form_data.get('code', '').strip() or f"WH-{abs(hash(name + str(datetime.utcnow()))) % 10000:04d}"
        wh_type = form_data.get('type', 'sales').strip()
        
        if not name:
            return False, "El nombre del almacén es obligatorio."
            
        if wh_col.find_one({"code": code.upper()}):
            return False, f"Ya existe un almacén con el código {code.upper()}."
            
        try:
            wh_col.insert_one({
                "name": name,
                "code": code.upper(),
                "type": wh_type,
                "is_active": True,
                "created_at": datetime.utcnow()
            })
            return True, f"Almacén '{name}' creado con éxito."
        except Exception as e:
            return False, f"Error al crear el almacén: {str(e)}"
    
    @staticmethod
    def get_paginated_products(company_db_name, filters=None, page=1, per_page=15, include_pricing=True):
        """
        `include_pricing=False` oculta costo/precio/margen/IVA de los documentos
        devueltos — usado por el módulo de Almacén para que un Almacenista pueda
        ver stock/lotes/vencimientos sin exponer información comercial sensible.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        products_col = db['products']
        query = {"is_active": {"$ne": False}}

        target_warehouse_id = None
        stock_filter = ''
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

            target_warehouse_id = filters.get('warehouse_id', '').strip()
            if target_warehouse_id and target_warehouse_id != "all":
                warehouse_filter = [
                    {f"stock_by_warehouse.{target_warehouse_id}": {"$exists": True, "$gt": 0}},
                    {f"stock_by_warehouse.{str(target_warehouse_id)}": {"$exists": True, "$gt": 0}}
                ]
                if "$or" in query:
                    query = {"$and": [query, {"$or": warehouse_filter}]}
                else:
                    query["$or"] = warehouse_filter

            stock_filter = (filters.get('stock_filter') or '').strip().lower()
            if stock_filter in ('zero', 'low'):
                if target_warehouse_id and target_warehouse_id != "all":
                    stock_expr = {"$ifNull": [f"$stock_by_warehouse.{target_warehouse_id}", 0]}
                else:
                    stock_expr = {"$ifNull": ["$stock", 0]}

                if stock_filter == 'zero':
                    query["$expr"] = {"$lte": [stock_expr, 0]}
                else:  # 'low' — por debajo o igual al mínimo configurado (y mínimo > 0)
                    query["min_stock"] = {"$gt": 0}
                    query["$expr"] = {"$lte": [stock_expr, "$min_stock"]}

        try:
            skip = (page - 1) * per_page
            projection = {
                "name": 1, "sku": 1, "category": 1, "brand": 1,
                "cost": 1, "price": 1, "profit_margin": 1, "iva_rate": 1,
                "unit_type": 1, "stock_by_warehouse": 1, "reserved_by_warehouse": 1,
                "stock": 1, "image_url": 1,
                "batch": 1, "expiration_date": 1, "batches": 1, "min_stock": 1
            }
            cursor = products_col.find(query, projection).sort('name', 1).skip(skip).limit(per_page)
            products = list(cursor)
            
            for prod in products:
                prod['_id'] = str(prod['_id'])
                prod.setdefault('cost', 0.0)
                prod.setdefault('price', 0.0)
                prod.setdefault('profit_margin', 30.0)
                prod.setdefault('iva_rate', 16.0)
                prod.setdefault('category', 'Sin Categoría')
                prod.setdefault('sku', 'N/D')
                prod.setdefault('unit_type', 'unidad')
                prod.setdefault('brand', 'N/D')
                prod.setdefault('min_stock', 0.0)
                stock_by_wh = prod.setdefault('stock_by_warehouse', {})
                reserved_by_wh = prod.setdefault('reserved_by_warehouse', {})

                if target_warehouse_id and target_warehouse_id != "all":
                    prod['stock'] = float(stock_by_wh.get(target_warehouse_id, stock_by_wh.get(str(target_warehouse_id), 0.0)))
                    prod['reserved'] = float(reserved_by_wh.get(target_warehouse_id, reserved_by_wh.get(str(target_warehouse_id), 0.0)))
                else:
                    prod['stock'] = sum(float(v) for v in stock_by_wh.values()) if stock_by_wh else prod.get('stock', 0.0)
                    prod['reserved'] = sum(float(v) for v in reserved_by_wh.values()) if reserved_by_wh else 0.0
                prod['available'] = prod['stock'] - prod['reserved']

                # Disponible POR bodega (físico - reservado), para que el
                # catálogo del vendedor pueda mostrar la cantidad correcta al
                # filtrar por un almacén específico — antes este campo no se
                # enviaba y el frontend siempre veía 0 al elegir un almacén.
                warehouse_keys = set(stock_by_wh.keys()) | set(reserved_by_wh.keys())
                prod['availability_by_warehouse'] = {
                    wh: float(stock_by_wh.get(wh, 0.0)) - float(reserved_by_wh.get(wh, 0.0))
                    for wh in warehouse_keys
                }

                prod.setdefault('image_url', None)
                prod.setdefault('batch', 'N/A')
                prod.setdefault('expiration_date', 'N/A')

                batches = prod.setdefault('batches', [])
                pending_batches = [b for b in batches if float(b.get('qty', 0.0)) > 0]
                upcoming = sorted([b for b in pending_batches if b.get('exp_date')], key=lambda b: b['exp_date'])
                prod['nearest_batch'] = upcoming[0] if upcoming else (pending_batches[0] if pending_batches else None)
                prod['lot_count'] = len(pending_batches)

                if not include_pricing:
                    for sensitive_field in ('cost', 'price', 'profit_margin', 'iva_rate'):
                        prod.pop(sensitive_field, None)

            total_count = products_col.count_documents(query)
            return products, total_count
        except Exception as e:
            print(f"Error en catálogo multi-almacén: {e}")
            return [], 0

    @staticmethod
    def get_distinct_categories_and_brands(company_db_name):
        """Para poblar los <select> de filtro por Categoría/Marca con los valores
        reales en uso, en vez de texto libre."""
        db = get_company_db(company_db_name)
        if db is None:
            return [], []
        categories = sorted([c for c in db['products'].distinct('category', {"is_active": {"$ne": False}}) if c])
        brands = sorted([b for b in db['products'].distinct('brand', {"is_active": {"$ne": False}}) if b])
        return categories, brands

    @staticmethod
    def get_zero_stock_products(company_db_name, warehouse_id=None):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        query = {"is_active": {"$ne": False}}
        if warehouse_id and warehouse_id != "all":
            query["$or"] = [
                {f"stock_by_warehouse.{warehouse_id}": {"$exists": False}},
                {f"stock_by_warehouse.{warehouse_id}": 0},
                {f"stock_by_warehouse.{warehouse_id}": 0.0}
            ]
        else:
            query["stock"] = {"$lte": 0}
        
        products = list(db['products'].find(query))
        for p in products:
            p['_id'] = str(p['_id'])
        return products

    @staticmethod
    def get_low_stock_products(company_db_name, warehouse_id=None):
        """
        Artículos con existencia en o por debajo de su stock mínimo configurado.
        Si se especifica warehouse_id, valida min_stock contra la existencia de ESE
        almacén puntual (stock_by_warehouse.<id>) en lugar del stock total agregado.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return []

        base_match = {"is_active": {"$ne": False}, "min_stock": {"$gt": 0}}

        if warehouse_id and warehouse_id != "all":
            stock_expr = {"$ifNull": [f"$stock_by_warehouse.{warehouse_id}", 0]}
        else:
            stock_expr = {"$ifNull": ["$stock", 0]}

        pipeline = [
            {"$match": base_match},
            {"$match": {"$expr": {"$lte": [stock_expr, "$min_stock"]}}}
        ]
        products = list(db['products'].aggregate(pipeline))
        for p in products:
            p['_id'] = str(p['_id'])
        return products

    @staticmethod
    def get_stock_alert_counts(company_db_name, warehouse_id=None):
        """Conteos ligeros para banners de alerta (sin traer documentos completos)."""
        zero_count = len(CommercialService.get_zero_stock_products(company_db_name, warehouse_id))
        low_count = len(CommercialService.get_low_stock_products(company_db_name, warehouse_id))
        return {"zero_stock_count": zero_count, "low_stock_count": low_count}

    @staticmethod
    def get_paginated_purchase_orders(company_db_name, filters=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        purchases_col = db['purchase_orders']

        match = {}
        if filters:
            warehouse_id = (filters.get('warehouse_id') or '').strip()
            if warehouse_id:
                match['warehouse_id'] = warehouse_id

            date_from = (filters.get('date_from') or '').strip()
            date_to = (filters.get('date_to') or '').strip()
            if date_from or date_to:
                date_query = {}
                if date_from:
                    try:
                        date_query["$gte"] = datetime.strptime(date_from, '%Y-%m-%d')
                    except ValueError:
                        pass
                if date_to:
                    try:
                        date_query["$lte"] = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    except ValueError:
                        pass
                if date_query:
                    match['timestamp'] = date_query

        search = (filters.get('search') or '').strip() if filters else ''
        post_lookup_match = None
        if search:
            post_lookup_match = {"$or": [
                {"supplier_name": {"$regex": search, "$options": "i"}},
                {"product.name": {"$regex": search, "$options": "i"}},
                {"product.sku": {"$regex": search, "$options": "i"}},
            ]}

        base_pipeline = [{"$match": match}] if match else []
        base_pipeline += [
            {"$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product"
            }},
            {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
        ]
        if post_lookup_match:
            base_pipeline.append({"$match": post_lookup_match})

        count_result = list(purchases_col.aggregate(base_pipeline + [{"$count": "total"}]))
        total_count = count_result[0]['total'] if count_result else 0

        skip = (page - 1) * per_page
        pipeline = base_pipeline + [
            {"$sort": {"timestamp": -1}},
            {"$skip": skip},
            {"$limit": per_page},
        ]
        orders = list(purchases_col.aggregate(pipeline))

        wh_names = {str(w['_id']): w.get('name') for w in db['warehouses'].find({}, {"name": 1})}
        for o in orders:
            o['_id'] = str(o['_id'])
            o['product_id'] = str(o['product_id'])
            o['product_name'] = o.get('product', {}).get('name', 'Artículo eliminado')
            o['product_sku'] = o.get('product', {}).get('sku', 'N/D')
            o['warehouse_name'] = wh_names.get(str(o.get('warehouse_id')), o.get('warehouse_id') or 'N/D')
            o.pop('product', None)

        return orders, total_count

    @staticmethod
    def register_purchase_order(company_db_name, form_data, user_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        product_id = form_data.get('product_id', '').strip()
        warehouse_id = form_data.get('warehouse_id', '').strip()
        supplier_name = form_data.get('supplier_name', 'Proveedor General').strip()
        batch_code = form_data.get('batch_code', '').strip() or None
        expiration_date = form_data.get('expiration_date', '').strip() or None

        try:
            quantity = float(form_data.get('quantity', 0))
            purchase_cost = float(form_data.get('purchase_cost', 0))
        except ValueError:
            return False, "Cantidad y costo de compra deben ser numéricos."

        if quantity <= 0 or purchase_cost < 0:
            return False, "La cantidad debe ser mayor a 0 y el costo válido."

        products_col = db['products']
        product = products_col.find_one({"_id": ObjectId(product_id)})
        if not product:
            return False, "Artículo no encontrado para la compra."

        batches = product.get('batches', [])
        _add_stock_batch(batches, warehouse_id, quantity, batch_code, expiration_date)
        stock_by_wh = _recompute_stock_by_warehouse(batches)
        total_stock = sum(stock_by_wh.values())

        purchase_record = {
            "product_id": ObjectId(product_id),
            "supplier_name": supplier_name,
            "quantity": quantity,
            "unit_cost": purchase_cost,
            "total_cost": quantity * purchase_cost,
            "warehouse_id": warehouse_id,
            "user": user_email,
            "timestamp": datetime.utcnow()
        }

        try:
            db['purchase_orders'].insert_one(purchase_record)
            products_col.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {
                    "cost": purchase_cost,
                    "batches": batches,
                    "stock_by_warehouse": stock_by_wh,
                    "stock": total_stock,
                    "updated_at": datetime.utcnow()
                }}
            )
            return True, f"Compra de {quantity} unidades registrada con éxito. Recibo generado."
        except Exception as e:
            return False, f"Error al procesar la orden de compra: {str(e)}"

    @staticmethod
    def _upload_product_image_to_r2(file_storage, rif, sku):
        return None

    @staticmethod
    def create_commercial_product(company_db_name, form_data, creator_email, image_file=None, rif=""):
        db = get_company_db(company_db_name)
        if db is None:
            return False, f"Base de datos de la empresa no disponible."
            
        products_col = db['products']
        product_id = form_data.get('product_id', '').strip()
        
        name = form_data.get('name', '').strip()
        sku = form_data.get('sku', '').strip() or f"SKU-{abs(hash(name + str(datetime.utcnow()))) % 100000:05d}"
        category = form_data.get('category', 'General').strip()
        brand = form_data.get('brand', '').strip()
        warehouse_id = form_data.get('warehouse_id', '').strip()
        batch = form_data.get('batch', '').strip() or 'N/A'
        expiration_date = form_data.get('expiration_date', '').strip() or 'N/A'
        
        try:
            cost = float(form_data.get('cost', 0) or 0)
            iva_rate = float(form_data.get('iva_rate', 16) or 16)
            initial_stock = float(form_data.get('stock', 0) or 0)
            min_stock = float(form_data.get('min_stock', 0) or 0)
            
            manual_price = form_data.get('price', '').strip()
            manual_margin = form_data.get('profit_margin', '').strip()
            
            if manual_price:
                price = float(manual_price)
                if cost > 0 and price > cost:
                    base_without_iva = price / (1 + (iva_rate / 100.0))
                    profit_margin = ((base_without_iva - cost) / cost) * 100.0
                else:
                    profit_margin = 0.0
            elif manual_margin:
                profit_margin = float(manual_margin)
                subtotal_margin = cost * (1 + (profit_margin / 100.0))
                price = subtotal_margin * (1 + (iva_rate / 100.0))
            else:
                profit_margin = 30.0
                subtotal_margin = cost * (1 + (profit_margin / 100.0))
                price = subtotal_margin * (1 + (iva_rate / 100.0))
                
        except ValueError:
            return False, "Los campos numéricos deben ser válidos."
            
        unit_type = form_data.get('unit_type', 'unidad').strip()

        try:
            weight_kg = float(form_data.get('weight_kg', 0) or 0)
        except ValueError:
            weight_kg = 0.0

        if not name:
            return False, "El nombre del artículo es obligatorio."

        image_url = None
        if image_file and image_file.filename:
            image_url = CommercialService._upload_product_image_to_r2(image_file, rif, sku)

        try:
            if product_id:
                update_data = {
                    "name": name,
                    "sku": sku,
                    "category": category,
                    "brand": brand,
                    "cost": cost,
                    "iva_rate": iva_rate,
                    "profit_margin": profit_margin,
                    "price": price,
                    "unit_type": unit_type,
                    "min_stock": min_stock,
                    "weight_kg": weight_kg,
                    "batch": batch,
                    "expiration_date": expiration_date,
                    "updated_at": datetime.utcnow()
                }
                if image_url:
                    update_data["image_url"] = image_url
                    
                products_col.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
                return True, f"Artículo '{name}' actualizado con éxito."
            else:
                stock_by_warehouse = {}
                batches = []
                if warehouse_id and initial_stock > 0:
                    stock_by_warehouse[warehouse_id] = initial_stock
                    initial_batch_code = batch if batch and batch != 'N/A' else None
                    initial_exp_date = expiration_date if expiration_date and expiration_date != 'N/A' else None
                    _add_stock_batch(batches, warehouse_id, initial_stock, initial_batch_code, initial_exp_date)

                new_doc = {
                    "name": name,
                    "sku": sku,
                    "category": category,
                    "brand": brand,
                    "cost": cost,
                    "iva_rate": iva_rate,
                    "profit_margin": profit_margin,
                    "price": price,
                    "unit_type": unit_type,
                    "min_stock": min_stock,
                    "weight_kg": weight_kg,
                    "stock": initial_stock,
                    "stock_by_warehouse": stock_by_warehouse,
                    "batches": batches,
                    "batch": batch,
                    "expiration_date": expiration_date,
                    "image_url": image_url,
                    "is_active": True,
                    "created_by": creator_email,
                    "created_at": datetime.utcnow()
                }
                products_col.insert_one(new_doc)
                return True, f"Artículo '{name}' creado con éxito en el almacén seleccionado."
        except Exception as e:
            return False, f"Error al guardar el artículo: {str(e)}"

    @staticmethod
    def seed_demo_catalog(company_db_name, creator_email):
        """
        Crea (si falta) un almacén demo y un catálogo de ~18 productos lácteos
        con stock inicial, para poder probar pedidos/facturas de inmediato sin
        tener que dar de alta el catálogo a mano. Idempotente: no duplica
        productos cuyo SKU ya exista, ni crea un segundo almacén demo si ya
        hay alguno activo.
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        wh_col = db['warehouses']
        warehouse = wh_col.find_one({"is_active": {"$ne": False}})
        warehouse_created = False
        if not warehouse:
            wh_col.insert_one({
                "name": "Almacén Central", "code": "WH-DEMO", "type": "sales",
                "is_active": True, "created_at": datetime.utcnow(),
            })
            warehouse = wh_col.find_one({"code": "WH-DEMO"})
            warehouse_created = True
        warehouse_id = str(warehouse['_id'])

        products_col = db['products']
        products_created = 0
        for item in DEMO_PRODUCTS:
            if products_col.find_one({"sku": item["sku"]}):
                continue
            cost = item["cost"]
            iva_rate = 16.0
            profit_margin = ((item["price"] / (1 + iva_rate / 100.0)) - cost) / cost * 100.0 if cost else 0.0
            batches = []
            _add_stock_batch(batches, warehouse_id, item["stock"], f"L-{item['sku']}", None)
            products_col.insert_one({
                "name": item["name"], "sku": item["sku"], "category": item["category"],
                "brand": "Lácteos Danny", "cost": cost, "iva_rate": iva_rate,
                "profit_margin": round(profit_margin, 2), "price": item["price"],
                "unit_type": item["unit_type"], "min_stock": 10.0,
                "weight_kg": item.get("weight_kg", 0.0),
                "stock": item["stock"], "stock_by_warehouse": {warehouse_id: item["stock"]},
                "batches": batches, "batch": "N/A", "expiration_date": "N/A",
                "image_url": None, "is_active": True,
                "created_by": creator_email, "created_at": datetime.utcnow(), "is_demo": True,
            })
            products_created += 1

        message = (
            f"Catálogo demo listo: {'almacén Central creado, ' if warehouse_created else ''}"
            f"{products_created} producto(s) nuevo(s) creado(s)."
        )
        return True, message

    @staticmethod
    def register_movement(company_db_name, form_data, user_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        product_id = form_data.get('product_id', '').strip()
        raw_type = form_data.get('movement_type', 'ENTRADA').strip()
        movement_type = CommercialService.MOVEMENT_ALIASES.get(raw_type, raw_type.upper())

        source_warehouse = form_data.get('source_warehouse_id', '').strip() or form_data.get('source_warehouse', '').strip()
        target_warehouse = form_data.get('target_warehouse_id', '').strip() or form_data.get('target_warehouse', '').strip()
        batch_code = form_data.get('batch_code', '').strip() or None
        expiration_date = form_data.get('expiration_date', '').strip() or None
        justification_note = form_data.get('notes', '').strip()

        if movement_type not in {'ENTRADA', 'SALIDA', 'TRASLADO', 'CARGO', 'DESCARGO'}:
            return False, "Tipo de movimiento no válido."

        if movement_type in CommercialService.MOVEMENTS_REQUIRING_ACTA and not justification_note:
            return False, "Los ajustes de Cargo/Descargo requieren un Acta o Nota de Justificación obligatoria."

        try:
            quantity = float(form_data.get('quantity', 0.0))
        except ValueError:
            return False, "La cantidad debe ser numérica."

        if quantity <= 0:
            return False, "La cantidad debe ser mayor a cero."

        products_col = db['products']
        product = products_col.find_one({"_id": ObjectId(product_id)})
        if not product:
            return False, "Artículo no encontrado."

        batches = product.get('batches', [])
        consumed = []

        if movement_type in ('ENTRADA', 'CARGO'):
            target_wh = target_warehouse or source_warehouse
            if not target_wh:
                return False, "Debe especificar el almacén destino para la entrada."
            batch_code = _add_stock_batch(batches, target_wh, quantity, batch_code, expiration_date)
            resolved_warehouse = target_wh

        elif movement_type in ('SALIDA', 'DESCARGO'):
            if not source_warehouse:
                return False, "Debe especificar el almacén de origen."
            ok, err, consumed = _consume_stock_batches(batches, source_warehouse, quantity, batch_code)
            if not ok:
                return False, err
            resolved_warehouse = source_warehouse

        elif movement_type == 'TRASLADO':
            if not source_warehouse or not target_warehouse:
                return False, "Debe especificar el almacén de origen y destino para el traslado."
            if source_warehouse == target_warehouse:
                return False, "El almacén de origen y destino no pueden ser el mismo."

            ok, err, consumed = _consume_stock_batches(batches, source_warehouse, quantity, batch_code)
            if not ok:
                return False, err
            for item in consumed:
                _add_stock_batch(batches, target_warehouse, item['qty'], item['batch_code'], item['exp_date'])
            resolved_warehouse = f"{source_warehouse} -> {target_warehouse}"

        stock_by_wh = _recompute_stock_by_warehouse(batches)
        total_stock = sum(stock_by_wh.values())

        try:
            products_col.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {
                    "batches": batches,
                    "stock_by_warehouse": stock_by_wh,
                    "stock": total_stock,
                    "updated_at": datetime.utcnow()
                }}
            )
            CommercialService._log_movement(
                db, product_id, movement_type, quantity, resolved_warehouse,
                user_email, justification_note, batch_code, consumed
            )
            return True, f"Movimiento '{movement_type}' procesado con éxito. Stock total: {total_stock}"
        except Exception as e:
            return False, f"Error al procesar el movimiento: {str(e)}"

    @staticmethod
    def _log_movement(db, product_id, action_type, quantity, warehouse_id, user_email, notes="", batch_code=None, consumed_detail=None):
        try:
            db['commercial_movements'].insert_one({
                "product_id": ObjectId(product_id),
                "action_type": action_type,
                "quantity": quantity,
                "warehouse_id": warehouse_id,
                "batch_code": batch_code,
                "consumed_detail": consumed_detail or [],
                "requires_acta": action_type in CommercialService.MOVEMENTS_REQUIRING_ACTA,
                "user": user_email,
                "notes": notes,
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            print(f"Error en auditoría comercial: {e}")

    @staticmethod
    def reserve_stock_for_order(company_db_name, warehouse_id, items):
        """
        Bloquea (reserva) la mercancía de un Pedido para que no pueda venderse dos
        veces mientras se verifica/factura. `items` = [{product_id, quantity}, ...].
        No toca stock_by_warehouse/batches (eso solo cambia al facturar de verdad) —
        solo incrementa product.reserved_by_warehouse[warehouse_id].
        Si algún artículo no tiene suficiente disponible, no reserva nada (todo o nada).
        Retorna (ok, mensaje).
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        products_col = db['products']
        reserved_so_far = []

        for item in items:
            product_id = item['product_id']
            quantity = float(item['quantity'])
            product = products_col.find_one({"_id": ObjectId(product_id)})
            if not product:
                CommercialService._rollback_reservations(products_col, warehouse_id, reserved_so_far)
                return False, "Uno de los artículos del pedido ya no existe."

            available = get_available_quantity(product, warehouse_id)
            if available < quantity:
                CommercialService._rollback_reservations(products_col, warehouse_id, reserved_so_far)
                return False, f"Stock disponible insuficiente para '{product.get('name')}' (Disponible: {available})."

            reserved_by_wh = product.get('reserved_by_warehouse', {})
            _reserve_quantity(reserved_by_wh, warehouse_id, quantity)
            products_col.update_one(
                {"_id": product['_id']},
                {"$set": {"reserved_by_warehouse": reserved_by_wh, "updated_at": datetime.utcnow()}}
            )
            reserved_so_far.append({"product_id": product_id, "quantity": quantity})

        return True, "Mercancía reservada con éxito para el pedido."

    @staticmethod
    def _rollback_reservations(products_col, warehouse_id, reserved_items):
        for item in reserved_items:
            product = products_col.find_one({"_id": ObjectId(item['product_id'])})
            if not product:
                continue
            reserved_by_wh = product.get('reserved_by_warehouse', {})
            _release_quantity(reserved_by_wh, warehouse_id, item['quantity'])
            products_col.update_one(
                {"_id": product['_id']},
                {"$set": {"reserved_by_warehouse": reserved_by_wh, "updated_at": datetime.utcnow()}}
            )

    @staticmethod
    def release_stock_for_order(company_db_name, warehouse_id, items):
        """
        Libera (reincorpora al disponible) la mercancía previamente reservada de un
        Pedido anulado o convertido a factura. `items` = [{product_id, quantity}, ...].
        """
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."

        products_col = db['products']
        for item in items:
            product = products_col.find_one({"_id": ObjectId(item['product_id'])})
            if not product:
                continue
            reserved_by_wh = product.get('reserved_by_warehouse', {})
            _release_quantity(reserved_by_wh, warehouse_id, float(item['quantity']))
            products_col.update_one(
                {"_id": product['_id']},
                {"$set": {"reserved_by_warehouse": reserved_by_wh, "updated_at": datetime.utcnow()}}
            )
        return True, "Mercancía liberada y reincorporada al disponible."

    @staticmethod
    def soft_delete_product(company_db_name, product_id):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible."
        try:
            result = db['products'].update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            if result.modified_count > 0:
                return True, "Artículo inactivado correctamente."
            return False, "Artículo no encontrado."
        except Exception as e:
            return False, f"Error al inactivar: {str(e)}"