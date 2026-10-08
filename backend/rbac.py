"""
Control de acceso por ROL FIJO -> MÓDULOS PERMITIDOS, aplicado a nivel de
servidor (main.py:before_request), no solo como aviso de UI. El rol de cada
usuario sigue siendo texto libre (definido en /personal), así que aquí se
normaliza a un conjunto reducido de "familias" de rol conocidas; cualquier
texto de rol que NO reconozcamos se trata como acceso completo ('full') para
no romper cuentas ya creadas con un texto de rol distinto al esperado — es
una política conservadora para no bloquear por accidente, no una gracia.

Módulos (coinciden con los grupos del menú lateral en base.html):
  - comercial:   Pedidos, Catálogo, Compras, Clientes, Facturación
  - finanzas:    Centro de Mando, Cuentas por Cobrar, Tesorería
  - operaciones: Talento/Personal, Logística & Rutas
  - almacen:     Almacén (stock, lotes, vencimientos, movimientos)
"""

MODULES = {'comercial', 'finanzas', 'operaciones', 'almacen'}
FULL_ACCESS = frozenset(MODULES)

# Alias de texto libre -> familia de rol conocida.
ROLE_ALIASES = {
    'almacenista': 'almacen',
    'almacen': 'almacen',
    'almacén': 'almacen',
    'warehouse': 'almacen',
    'supervisor de almacén': 'almacen_supervisor',
    'supervisor de almacen': 'almacen_supervisor',
    'tesorería': 'finanzas',
    'tesoreria': 'finanzas',
    'tesorería / cobranzas': 'finanzas',
    'tesoreria / cobranzas': 'finanzas',
    'cobranzas': 'finanzas',
    'chofer': 'operaciones',
    'conductor': 'operaciones',
    'chofer / conductor': 'operaciones',
    'seller': 'comercial',
    'vendedor': 'comercial',
    'vendedor (app móvil)': 'comercial',
    'vendedor (app movil)': 'comercial',
    'cashier': 'comercial',
    'cajero': 'comercial',
    'facturador': 'comercial',
    'facturador / cajero': 'comercial',
    'gerente de ventas': 'comercial_operaciones',
    'admin': 'full',
    'administrador': 'full',
    'administrador general': 'full',
    'gerente': 'full',
}

ROLE_FAMILY_MODULES = {
    'full': FULL_ACCESS,
    'comercial': {'comercial'},
    'finanzas': {'finanzas'},
    'operaciones': {'operaciones'},
    'almacen': {'almacen'},
    'almacen_supervisor': {'almacen', 'comercial'},
    'comercial_operaciones': {'comercial', 'operaciones'},
}

# Prefijo de ruta -> módulo. Se evalúa en orden: el primer prefijo que
# coincida gana (por eso las rutas de Finanzas van antes que /commercial a
# secas, ya que ambas cuelgan del mismo blueprint).
PATH_MODULE_RULES = [
    ('/commercial/financial', 'finanzas'),
    ('/commercial/receivables', 'finanzas'),
    ('/commercial/treasury', 'finanzas'),
    ('/commercial', 'comercial'),
    ('/almacen', 'almacen'),
    ('/inventory', 'almacen'),
    ('/personal', 'operaciones'),
    ('/logistics', 'operaciones'),
]

# Rutas que cualquier usuario autenticado puede ver sin importar su rol
# (login, dashboard ejecutivo, logout, estáticos).
EXEMPT_PREFIXES = ('/static', '/dashboard', '/logout', '/register-business', '/api/')


def get_allowed_modules(role):
    """Retorna el set de módulos permitidos para un rol (texto libre)."""
    family = ROLE_ALIASES.get((role or '').strip().lower())
    if family is None:
        return FULL_ACCESS
    return ROLE_FAMILY_MODULES.get(family, FULL_ACCESS)


def module_for_path(path):
    """Resuelve a qué módulo pertenece una ruta, o None si no aplica (rutas
    exentas o fuera de los 4 módulos controlados, ej. '/', '/dashboard')."""
    if path == '/' or any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return None
    for prefix, module in PATH_MODULE_RULES:
        if path.startswith(prefix):
            return module
    return None


def is_warehouse_only_role(role):
    """Compatibilidad: usado por commercial_routes.py para redirigir al
    Almacenista fuera del Catálogo administrativo con un mensaje específico,
    antes incluso de que el before_request global bloquee la ruta."""
    return get_allowed_modules(role) == {'almacen'}
