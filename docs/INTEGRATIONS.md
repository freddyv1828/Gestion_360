# Documentación para Integraciones Futuras — Gestión 360

Este documento define el contrato de integración para (1) la futura App Móvil de
vendedores/clientes y (2) la sincronización del catálogo de dropshipping Dropi.
Describe lo que **ya existe** en el código (`backend/routes/api_routes.py`,
`backend/services/dropi_service.py`, `backend/services/marketplace_service.py`,
`backend/services/login_service.py`) y lo que queda **propuesto** para la siguiente
fase de desarrollo.

---

## 1. Integración App Móvil (API REST)

### 1.1 Autenticación

- Ya implementado: `POST /api/v1/auth/login` (`api_routes.py`) — recibe
  `{ "email", "password" }`, valida contra el Directorio Global Central
  (`login_service.login_business_user`) y responde con un **JWT** (`PyJWT`,
  `JWT_SECRET_KEY`, expiración 30 días) más el perfil del usuario. Si el usuario es
  vendedor/staff de empresa (`user_type` en `seller`/`company_staff`), la respuesta
  incluye además el inventario completo de su empresa para descarga inicial
  (`MarketplaceService.get_company_inventory_for_seller`).
- Ya implementado: decorador `@jwt_required` (`api_routes.py`) — exige
  `Authorization: Bearer <jwt>`, decodifica con `JWT_SECRET_KEY` e inyecta
  `request.jwt_user`. **`company_db` siempre se resuelve del token**, nunca de un
  parámetro de la URL/body, para que un vendedor nunca pueda leer el inventario de
  otra empresa suplantando el parámetro. Todos los endpoints `/api/v1/seller/*` lo
  usan.

### 1.2 Endpoints existentes

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/api/v1/auth/login` | — | Login unificado vendedor/cliente, emite JWT |
| GET | `/api/v1/marketplace/catalog` | Pública | Vitrina Dropi para *guest browsing* |
| POST | `/api/v1/marketplace/checkout` | — | Carrito → pedido, con alta/login en caliente del cliente |
| GET | `/api/v1/seller/dashboard` | JWT | Resumen: clientes, pedidos abiertos, cuentas por cobrar |
| GET/POST | `/api/v1/seller/clients` | JWT | Listar / crear clientes de la empresa |
| GET | `/api/v1/seller/products` | JWT | Catálogo paginado (filtro de almacén/búsqueda) |
| GET | `/api/v1/seller/warehouses` | JWT | Almacenes de la empresa |
| GET/POST | `/api/v1/seller/orders` | JWT | Listar / crear Pedidos (bloquea stock al crear) |
| GET | `/api/v1/seller/orders/<id>` | JWT | Detalle de un pedido |
| POST | `/api/v1/seller/orders/<id>/cancel` | JWT | Anula y libera la reserva de stock |
| GET/POST | `/api/v1/seller/budgets` | JWT | Presupuestos/cotizaciones (NO tocan stock) |
| POST | `/api/v1/seller/budgets/<id>/convert` | JWT | Convierte presupuesto en Pedido real |
| GET | `/api/v1/seller/accounts-receivable` | JWT | Cartera por cobrar de la empresa |

### 1.3 Endpoints propuestos para la siguiente fase

**`GET /api/v1/products`** — Catálogo paginado con filtro de almacén, para que la App
Móvil liste y busque productos sin descargar todo el catálogo de una vez.

```
GET /api/v1/products?warehouse_id=<id|all>&search=&category=&page=1&per_page=20
Headers: Authorization: Bearer <jwt>

200 OK
{
  "products": [
    {
      "_id": "...", "name": "...", "sku": "...", "price": 12.5,
      "stock": 34, "unit_type": "unidad",
      "nearest_batch": { "batch_code": "L-240501", "exp_date": "2026-05-01" }
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total_count": 134, "total_pages": 7 }
}
```

Implementación sugerida: reutilizar directamente
`CommercialService.get_paginated_products(company_db_name, filters, page, per_page)`
— ya soporta paginación real (`skip`/`limit`) y filtro por almacén, por lo que este
endpoint es una capa delgada de serialización JSON sobre un servicio ya existente.

**`POST /api/v1/movements`** — Registro rápido de entradas/salidas desde la App Móvil
(lector de código de barras/lotes en bodega o punto de entrega).

```
POST /api/v1/movements
Headers: Authorization: Bearer <jwt>
Body:
{
  "product_id": "...", "movement_type": "SALIDA",
  "source_warehouse_id": "...", "quantity": 5,
  "batch_code": null,            // null => se resuelve por FEFO
  "notes": "Entrega ruta móvil #123"
}

200 OK  { "message": "Movimiento 'SALIDA' procesado con éxito. Stock total: 29" }
400 Bad Request  { "error": "Stock insuficiente en el almacén/lote seleccionado..." }
```

Implementación sugerida: capa delgada sobre
`CommercialService.register_movement(company_db_name, form_data, user_email)` (ya
contiene la validación de Acta obligatoria para CARGO/DESCARGO y el consumo FEFO).
`company_db_name` y `user_email` se derivan del JWT decodificado, nunca del body.

### 1.4 Seguridad

- Toda la comunicación debe ser HTTPS en producción.
- El JWT ya usa `JWT_SECRET_KEY` (variable de entorno `.env`) — rotar este secreto
  invalida todas las sesiones móviles activas.
- Es recomendable añadir un *rate limit* básico (p. ej. Flask-Limiter) a
  `/api/v1/auth/login` para mitigar fuerza bruta antes de exponer la API públicamente.

---

## 2. Integración Catálogo Dropi (Dropshipping)

### 2.1 Estado actual

`backend/services/dropi_service.py` ya implementa:

- `ensure_virtual_warehouse(company_db_name)` — crea (idempotente) el **Almacén
  Virtual Dropi** (`code="WH-DROPI"`, `type="dropshipping"`) dentro de la empresa.
- `sync_catalog_to_marketplace()` — sincroniza el catálogo hacia
  `gestion360_marketplace.dropi_catalog`. Si `DROPI_API_KEY` no está configurada en
  `.env`, siembra un catálogo de prueba (`_MOCK_CATALOG`) para no bloquear el
  desarrollo de la vitrina móvil.
- Disparador manual ya conectado en la UI: botón **"Sincronizar Dropi"** en
  `commercial/products.html` → `POST /commercial/dropi/sync`.

### 2.2 Mapeo de campos (Dropi → Gestión 360)

| Campo Dropi | Campo interno (`dropi_catalog` / `products`) | Notas |
|---|---|---|
| SKU externo (`dropi_sku`) | `dropi_sku` | Identificador único de upsert |
| Nombre del producto | `name` | — |
| Costo de proveedor | `price` (fuente) → mapear a `cost` al importar al catálogo de la empresa | El costo de proveedor Dropi se usa como `cost`, nunca como precio de venta directo |
| Precio sugerido | — (propuesto) | Añadir campo `suggested_price` en `dropi_catalog`; al importar, aplicar el mismo motor de margen (`profit_margin`/IVA) que `create_commercial_product` |
| Stock | `stock` | Se refleja como `stock_by_warehouse[WH-DROPI]` del almacén virtual |

### 2.3 Propuesta de sincronización programada (`sync_dropi`)

Actualmente la sincronización es manual (botón en UI). Para producción se propone:

1. **Webhook** (preferido si Dropi lo soporta): Dropi notifica
   `POST /api/v1/dropi/webhook` en cada cambio de stock/precio de un producto
   suscrito; el handler actualiza únicamente el documento afectado en
   `dropi_catalog` (y en `products` si ya fue importado al Almacén Virtual).
2. **Polling periódico** (fallback / complemento): tarea programada que invoca
   `DropiService.sync_catalog_to_marketplace()` cada N minutos vía APScheduler
   (proceso en background del propio Flask) o un cron job externo que golpee un
   endpoint protegido `POST /api/v1/dropi/sync` con un token de servicio
   (no de usuario).
3. En ambos casos, los productos importados deben quedar marcados con
   `source: "dropi_api"` (ya existe ese campo) para diferenciarlos del inventario
   propio y poder excluirlos de ciertos reportes (p. ej. costos reales vs.
   dropshipping).

### 2.4 Siguiente paso operativo

Antes de integrar el catálogo real de Dropi, configurar en `backend/.env`:

```
DROPI_API_BASE_URL=https://api.dropi.co
DROPI_API_KEY=<token real de la cuenta Dropi>
```

Con la key configurada, `sync_catalog_to_marketplace()` deja de usar el catálogo de
prueba (`_MOCK_CATALOG`) y consulta `GET {DROPI_API_BASE_URL}/api/products`
automáticamente.
