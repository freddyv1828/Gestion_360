"""
Exportación genérica CSV (compatible con Excel — se abre nativo, sin
dependencias binarias extra como openpyxl) reutilizable por cualquier módulo
con listados: Productos/Almacén, Clientes, Pedidos, Facturas, Compras,
Logística, Financiero.
"""
import csv
import io


def rows_to_csv(rows, headers_map):
    """
    `headers_map`: dict ordenado {clave_campo: "Encabezado Visible"}.
    `rows`: lista de dicts (acceso con .get, no rompe si falta una clave).
    Retorna bytes (UTF-8 con BOM para que Excel detecte acentos correctamente).
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(list(headers_map.values()))
    for row in rows:
        writer.writerow([row.get(k, '') for k in headers_map.keys()])
    return output.getvalue().encode('utf-8-sig')
