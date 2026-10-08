"""
Catálogo fijo de cuentas contables para clasificar CADA movimiento de
Tesorería (cobro = ingreso, pago = gasto) — el mismo plan de cuentas que ya
usa la empresa en su control manual por Excel. Mantenido como lista plana
(no editable desde la UI) a propósito: es contabilidad, no debe cambiar por
accidente.
"""

INCOME_CATEGORIES = [
    "INGRESO POR VENTAS",
    "OTROS INGRESOS",
    "INGRESOS POR IDENTIFICAR",
]

EXPENSE_CATEGORIES = [
    "COMPRA MERCANCIA",
    "GASTOS DE PAPELERIA",
    "GASTOS MATERIAL DE LIMPIEZA",
    "GASTOS DE INSUMOS CAFETERIA",
    "GASTOS SERV BASICOS",
    "GASTOS DE LIMPIEZA",
    "OTROS GASTOS",
    "ALQUILER LOCAL",
    "GASTOS DE REMODELACION",
    "GASTOS MANT DE EQUIPOS",
    "GASTOS DE COMBUSTIBLE",
    "COMISIONES BANCARIAS",
    "COMISION VENDEDORES",
    "GASTOS PERSONALES",
    "MOBIL. Y EQUI. DE OFICINA",
    "PUBLICIDAD Y PROPAGANDA",
    "GASTOS SUELDOS Y SALARIOS",
    "GASTOS HONORARIOS",
    "COMPRA DOLARES",
    "VIATICOS VENDEDORES",
    "VIATICOS DESPACHOS",
    "MANT Y REPARACION DE VEHICULO",
    "PAGO DE IMPUESTOS",
    "PRESTAMOS PERSONALES",
    "FLETES EXTERNOS",
    "PRESTACIONES SOCIALES",
    "GASTOS POR IDENTIFICAR",
    "AGASAJO AL PERSONAL",
    "GASTOS DE COMERCIALIZACION",
    "CREDITO BANCARIO",
    "SERVICIOS SISTEMAS Y PROGRAMAS",
    "SERVICIOS DE LIMPIEZA",
    "DOTACION AL PERSONAL",
    "DONACIONES",
    "BONIFICACIONES",
    "REINTEGRO DE CLIENTES",
    "OPERACION FINANCIERA",
    "GASTOS DE ENCOMIENDA Y ENVIOS",
    "CUENTAS POR COBRAR ACCIONISTA",
    "OTRAS CUENTAS POR COBRAR",
    "CUENTAS TRANSITORIAS",
    "SERVICIO DE REFRIGERACION Y ALMACENAJE",
    "PEAJES",
    "TRANSFERENCIAS ENTRE CUENTAS",
    "GASTOS ADMINISTRATIVOS",
    "GASTOS DE DESPACHO",
    "GASTO DE VACACIONES Y BONO VACACIONAL",
    "GASTOS MTTO. INSTALACIONES",
    "CAPACITACION Y ENTRENAMIENTO AL PERSONAL",
    "GASTOS DE OPERACION Y LOGISTICA",
]

ALL_CATEGORIES = INCOME_CATEGORIES + EXPENSE_CATEGORIES

DEFAULT_INCOME_CATEGORY = "INGRESOS POR IDENTIFICAR"
DEFAULT_EXPENSE_CATEGORY = "GASTOS POR IDENTIFICAR"


def default_category_for(tx_type):
    """Cuenta contable de respaldo cuando no se especificó ninguna — nunca
    debe quedar un movimiento sin clasificar, aunque sea en 'por identificar'."""
    return DEFAULT_INCOME_CATEGORY if tx_type == "COBRO" else DEFAULT_EXPENSE_CATEGORY


def normalize_category(category, tx_type):
    category = (category or "").strip().upper()
    if category in ALL_CATEGORIES:
        return category
    return default_category_for(tx_type)
