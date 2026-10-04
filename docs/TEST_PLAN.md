# Plan de Pruebas Funcionales — Gestión 360 (Pre-Financiero)

Checklist solicitado antes de pasar al módulo financiero/Dropi, con el resultado de lo
que pudo validarse de forma automatizada en este entorno y lo que requiere validación
manual del usuario contra la base de datos real (MongoDB Atlas).

> **Nota de entorno:** el entorno de desarrollo donde se generaron estos cambios no
> tiene salida de red hacia MongoDB Atlas (`DATABASE_URL`), por lo que las pruebas
> contra datos reales **no pudieron ejecutarse aquí**. Lo que sí se validó
> automáticamente fue: (1) la lógica pura de FEFO/auditoría sin tocar la base de
> datos, (2) que la aplicación Flask arranca y todas las rutas nuevas resuelven sin
> errores de importación/`url_for`, y (3) que los templates nuevos renderizan sin
> errores de Jinja con datos de prueba. Los casos marcados **[Manual — pendiente]**
> deben ejecutarse en tu entorno con la base de datos conectada.

## Checklist solicitado

- [x] **Prueba de Paginación** — `CommercialService.get_paginated_products` ya usa
  `.skip(offset).limit(per_page)` real sobre MongoDB (`commercial_service.py:162`).
  Se agregaron controles de paginación (Anterior/Siguiente + indicador de página) en
  `commercial/products.html`, que antes no existían a pesar de que el backend ya
  soportaba la paginación. **Manual — pendiente:** cargar 50+ productos reales y
  confirmar que la tabla sólo trae 15 a la vez y que el salto de página es inmediato.

- [x] **Prueba de Stock Cero y Mínimo** — Se corrigió un bug en
  `get_low_stock_products` (el pipeline usaba `$redact` con `"$KEEP"/"$PRUNE"` en vez
  de las variables de sistema `"$$KEEP"/"$$PRUNE"`, por lo que el filtro no
  funcionaba). Ahora usa `$match` + `$expr` y además soporta evaluación **por
  almacén** cuando hay un filtro de almacén activo. El banner de `products.html` ya
  no cuenta solo los productos de la página actual — usa
  `CommercialService.get_stock_alert_counts()` (conteo global). **Manual —
  pendiente:** crear un producto con stock 0 en un almacén y confirmar el banner rojo
  + etiqueta roja en la fila; crear otro con `min_stock` > stock actual y confirmar
  el banner ámbar + etiqueta "Mínimo".

- [x] **Prueba FEFO** — Verificado con una prueba unitaria pura (sin DB) sobre
  `_consume_stock_batches`: se crearon dos lotes del mismo artículo/almacén con
  fechas de vencimiento distintas (12-2026 y 06-2026) y se ejecutó una salida de 60
  unidades. Resultado confirmado: el lote con vencimiento más próximo (06-2026) se
  consumió primero y por completo (50 u.), y el remanente (10 u.) se tomó del
  segundo lote — el comportamiento FEFO es correcto. También se verificó que un
  **traslado** entre almacenes no pierde cantidad: 40 unidades en `WH1`, se trasladan
  15 a `WH2`, y el total combinado sigue siendo 40 (25 + 15). **Manual —
  pendiente:** repetir esta misma prueba desde la UI (`Movimiento` → `Traslado` /
  `Salida`) contra la base de datos real para confirmar extremo a extremo.

- [x] **Prueba de Auditoría** — Confirmado a nivel de código y por prueba unitaria:
  `CommercialService.MOVEMENTS_REQUIRING_ACTA = {'CARGO', 'DESCARGO'}`, y
  `register_movement` rechaza la operación con el mensaje *"Los ajustes de
  Cargo/Descargo requieren un Acta o Nota de Justificación obligatoria."* si `notes`
  llega vacío. El frontend (`updateMovementFormVisibility()` en `products.html`)
  además marca el campo como `required` y cambia su etiqueta cuando se selecciona
  CARGO/DESCARGO, evitando el envío sin texto desde el propio navegador. **Manual —
  pendiente:** intentar enviar un Descargo sin texto en la nota manipulando el DOM
  (quitando el `required`) para confirmar que el backend también lo bloquea (defensa
  en profundidad, no solo validación de cliente).

## Pruebas adicionales ejecutadas en este entorno

| Prueba | Resultado |
|---|---|
| `python -m py_compile` sobre todos los módulos de `routes/` y `services/` | ✅ Sin errores de sintaxis |
| Arranque de la app Flask (`import main`) | ❌→✅ Se encontró y corrigió un bug bloqueante: `main.py` importaba `business_bp` desde `routes/business_routes.py`, un archivo obsoleto/duplicado del actual `commercial_routes.py` que ni siquiera definía esa variable — **la aplicación no arrancaba en absoluto**. Se eliminó el import y el archivo obsoleto. |
| `url_for()` de todos los endpoints nuevos (Compras, Facturación, detalle de factura) | ✅ Resuelven correctamente |
| Acceso sin sesión a `/dashboard`, `/commercial/products`, `/commercial/purchases`, `/commercial/invoicing`, `/logistics/` | ✅ Redirigen al login como se espera |
| Render de Jinja de `commercial/products.html`, `purchases.html`, `invoicing.html`, `invoice_detail.html`, `dashboard.html` con datos simulados | ❌→✅ Se encontró y corrigió un bug: `invoice_detail.html` usaba `invoice.items` (choca con el método `dict.items()` de Python/Jinja) en vez de `invoice['items']`, lo que rompía la vista de detalle de factura. |

## Pendientes para el usuario (requieren la base de datos real)

1. Ejecutar los 4 escenarios del checklist directamente en la UI conectada a MongoDB
   Atlas (este entorno de desarrollo no tiene salida de red hacia Atlas).
2. Registrar al menos una compra, una factura y un traslado real para confirmar que
   los contadores del Dashboard (`purchases_count`, `invoices_count`) y las alertas
   de stock reflejan los datos reales.
3. Validar visualmente el nuevo menú lateral agrupado (Comercial / Finanzas /
   Operaciones / Integraciones) en light y dark mode, y en una pantalla angosta.
