import sqlalchemy
from utils import get_db_connection

def get_warehouses_service(company_rif):
    """Obtiene todos los almacenes creados por la empresa."""
    try:
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        warehouses_table = sqlalchemy.Table('warehouses', metadata, autoload_with=engine)

        with engine.connect() as connection:
            stmt = sqlalchemy.select(warehouses_table).where(warehouses_table.c.company_rif == company_rif)
            result = connection.execute(stmt).fetchall()
            return [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"Error al listar almacenes: {e}")
        return []

def create_warehouse_service(company_rif, name, description=""):
    """Permite al negocio crear un almacén dinámico nuevo."""
    try:
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        warehouses_table = sqlalchemy.Table('warehouses', metadata, autoload_with=engine)

        with engine.connect() as connection:
            insert_stmt = warehouses_table.insert().values(
                company_rif=company_rif,
                name=name,
                description=description
            )
            connection.execute(insert_stmt)
            connection.commit()
            return True, "Almacén creado con éxito"
    except Exception as e:
        print(f"Error al crear almacén: {e}")
        return False, str(e)

def get_products_service(company_rif):
    """Obtiene el catálogo de productos de la empresa."""
    try:
        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        products_table = sqlalchemy.Table('products', metadata, autoload_with=engine)

        with engine.connect() as connection:
            stmt = sqlalchemy.select(products_table).where(products_table.c.company_rif == company_rif)
            result = connection.execute(stmt).fetchall()
            return [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"Error al listar productos: {e}")
        return []

def create_product_service(company_rif, form_data, image_url=""):
    """Registra un producto soportando unidades o kilogramos y atributos flexibles."""
    try:
        name = form_data.get('name', '').strip()
        category = form_data.get('category', '').strip() # Para clasificación ABC
        price = float(form_data.get('price', 0.0))
        stock = float(form_data.get('stock', 0.0)) # Soporta decimales para kg o enteros para unidades
        unit_type = form_data.get('unit_type', 'unit') # 'unit' o 'kg'
        weight_str = form_data.get('weight', '1kg')

        engine = get_db_connection()
        metadata = sqlalchemy.MetaData()
        products_table = sqlalchemy.Table('products', metadata, autoload_with=engine)

        with engine.connect() as connection:
            insert_stmt = products_table.insert().values(
                company_rif=company_rif,
                name=name,
                category=category,
                price=price,
                stock=stock,
                unit_type=unit_type,
                image_url=image_url,
                attributes={"peso": weight_str}
            )
            connection.execute(insert_stmt)
            connection.commit()
            return True, "Producto registrado con éxito en el inventario"
    except Exception as e:
        print(f"Error al registrar producto: {e}")
        return False, str(e)