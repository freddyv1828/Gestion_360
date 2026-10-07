"""
Control de acceso simple basado en el rol guardado en la sesión
(session['user_role'], texto libre definido en /personal). No es un sistema de
permisos granular — solo resuelve el caso concreto pedido: un Almacenista no
debe poder ver costos/márgenes del Catálogo administrativo, solo su propio
módulo de Almacén (stock, lotes, vencimientos y movimientos).
"""

WAREHOUSE_ONLY_ROLES = {'almacenista', 'almacen', 'almacén', 'warehouse'}


def is_warehouse_only_role(role):
    return (role or '').strip().lower() in WAREHOUSE_ONLY_ROLES
