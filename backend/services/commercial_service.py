from datetime import datetime
from bson import ObjectId
import os
import unicodedata
import re
from database import get_company_db
from utils import get_r2_client, R2_BUCKET_NAME, R2_PUBLIC_DOMAIN


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
    def get_paginated_products(company_db_name, filters=None, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0
            
        products_col = db['products']
        query = {"is_active": {"$ne": False}}
        
        target_warehouse_id = None
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

        try:
            skip = (page - 1) * per_page
            projection = {
                "name": 1, "sku": 1, "category": 1, "brand": 1,
                "cost": 1, "price": 1, "profit_margin": 1, "iva_rate": 1,
                "unit_type": 1, "stock_by_warehouse": 1, "stock": 1, "image_url": 1,
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
                
                if target_warehouse_id and target_warehouse_id != "all":
                    prod['stock'] = float(stock_by_wh.get(target_warehouse_id, stock_by_wh.get(str(target_warehouse_id), 0.0)))
                else:
                    prod['stock'] = sum(float(v) for v in stock_by_wh.values()) if stock_by_wh else prod.get('stock', 0.0)

                prod.setdefault('image_url', None)
                prod.setdefault('batch', 'N/A')
                prod.setdefault('expiration_date', 'N/A')

                batches = prod.setdefault('batches', [])
                pending_batches = [b for b in batches if float(b.get('qty', 0.0)) > 0]
                upcoming = sorted([b for b in pending_batches if b.get('exp_date')], key=lambda b: b['exp_date'])
                prod['nearest_batch'] = upcoming[0] if upcoming else (pending_batches[0] if pending_batches else None)
                prod['lot_count'] = len(pending_batches)

            total_count = products_col.count_documents(query)
            return products, total_count
        except Exception as e:
            print(f"Error en catálogo multi-almacén: {e}")
            return [], 0

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
    def get_active_products_lite(company_db_name):
        """Lista ligera de artículos activos (para selects de Compras/Facturación)."""
        db = get_company_db(company_db_name)
        if db is None:
            return []
        projection = {"name": 1, "sku": 1, "price": 1, "cost": 1, "iva_rate": 1, "unit_type": 1, "stock": 1}
        products = list(db['products'].find({"is_active": {"$ne": False}}, projection).sort('name', 1))
        for p in products:
            p['_id'] = str(p['_id'])
            p.setdefault('price', 0.0)
            p.setdefault('cost', 0.0)
            p.setdefault('iva_rate', 16.0)
        return products

    @staticmethod
    def get_paginated_purchase_orders(company_db_name, page=1, per_page=15):
        db = get_company_db(company_db_name)
        if db is None:
            return [], 0

        purchases_col = db['purchase_orders']
        total_count = purchases_col.count_documents({})
        skip = (page - 1) * per_page

        pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$skip": skip},
            {"$limit": per_page},
            {"$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product"
            }},
            {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}}
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