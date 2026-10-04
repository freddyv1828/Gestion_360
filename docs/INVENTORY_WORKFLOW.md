# Flujo de Vida de la Mercancía — Gestión 360

Diagrama textual del ciclo operativo completo de inventario, desde el ingreso hasta la
salida, incluyendo el control de lotes (FEFO), traslados entre almacenes y las alertas
de stock. Corresponde a la lógica implementada en `backend/services/commercial_service.py`.

## Diagrama de flujo (paso a paso)

```
                          ┌───────────────────────────┐
                          │   1. INGRESO DE MERCANCÍA  │
                          │  (Compra a proveedor o      │
                          │   sincronización Dropi)     │
                          └──────────────┬───────────┘
                                         │
                   Commercial.register_purchase_order()
                   DropiService.sync_catalog_to_marketplace()
                                         │
                                         ▼
                  ┌───────────────────────────────────────┐
                  │ 2. ASIGNACIÓN A ALMACÉN + LOTE          │
                  │   - Selección del almacén destino       │
                  │   - Código de lote (manual o AUTO-xxxx)  │
                  │   - Fecha de vencimiento (opcional)      │
                  │   → _add_stock_batch()                   │
                  └──────────────────┬────────────────────┘
                                     │
                                     ▼
                  ┌───────────────────────────────────────┐
                  │ 3. CONSOLIDACIÓN DE STOCK                │
                  │   stock_by_warehouse[wh] = Σ lotes(wh)   │
                  │   stock total = Σ stock_by_warehouse     │
                  │   → _recompute_stock_by_warehouse()       │
                  └──────────────────┬────────────────────┘
                                     │
                     ┌───────────────┼────────────────────┐
                     ▼               ▼                    ▼
            ┌────────────────┐ ┌────────────┐   ┌────────────────────┐
            │ 4a. SALIDA      │ │4b. TRASLADO│   │4c. CARGO/DESCARGO   │
            │ (venta/factura, │ │entre        │   │(ajuste de inventario │
            │  merma, etc.)   │ │almacenes    │   │ — requiere Acta)     │
            └───────┬─────────┘ └─────┬──────┘   └──────────┬──────────┘
                    │                 │                     │
                    ▼                 ▼                     ▼
          _consume_stock_batches()  consume en origen   _consume_stock_batches()
          por FEFO (ordena por      + _add_stock_batch()  o _add_stock_batch()
          exp_date ascendente,      en destino (mismo     según sea DESCARGO/CARGO
          None al final) si no      lote/fecha, no se      — bloquea si falta
          se especifica lote        pierde trazabilidad)   justificación/Acta
                    │                 │                     │
                    └────────┬────────┴──────────┬──────────┘
                             ▼                    ▼
                  ┌─────────────────────────────────────────┐
                  │ 5. ACTUALIZACIÓN DE CONTADORES             │
                  │   - stock_by_warehouse recalculado          │
                  │   - stock total recalculado                 │
                  │   - registro en commercial_movements         │
                  │     (auditoría: usuario, acta, lotes          │
                  │      consumidos, fecha)                       │
                  └──────────────────┬──────────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────────┐
                  │ 6. EVALUACIÓN DE ALERTAS VISUALES           │
                  │   stock == 0            → Banner "Sin Stock"│
                  │   stock <= min_stock     → Banner "Mínimo"   │
                  │   (evaluado por almacén cuando se filtra)     │
                  │   → CommercialService.get_stock_alert_counts()│
                  └─────────────────────────────────────────┘
```

## Explicación del flujo

1. **Ingreso.** El inventario entra al sistema por dos vías: una orden de compra a
   proveedor (`CommercialService.register_purchase_order`, módulo **Compras**) o la
   sincronización programada del catálogo Dropi (`DropiService.sync_catalog_to_marketplace`,
   que alimenta el Almacén Virtual Dropi).

2. **Asignación a almacén y lote.** Cada entrada se asigna a un almacén físico (o
   virtual, en el caso de Dropi) y se registra como un lote (`batch_code` + `exp_date`).
   Si no se indica un código de lote, el sistema genera uno automático
   (`AUTO-YYYYMMDDHHMMSS`). Si el lote ya existe en ese almacén, su cantidad simplemente
   se incrementa (`_add_stock_batch`).

3. **Consolidación de stock.** Tras cada movimiento, `stock_by_warehouse` se recalcula
   sumando todos los lotes vivos (`qty > 0`) agrupados por almacén, y el `stock` total
   del artículo es la suma de todos los almacenes. Esto es lo que garantiza que la
   mercancía **nunca se pierda** al moverse: un traslado primero consume del almacén
   origen y automáticamente reinyecta la misma cantidad (con su mismo lote y fecha de
   vencimiento) en el almacén destino — nunca se descuenta sin su contraparte de alta.

4. **Operaciones de salida.** Al vender (factura), trasladar o dar de baja mercancía:
   - Si el usuario no especifica un lote manualmente, el sistema aplica **FEFO** (First
     Expired, First Out): ordena los lotes del almacén de origen por fecha de
     vencimiento ascendente (los que no tienen fecha quedan de últimos) y consume en
     ese orden hasta completar la cantidad solicitada.
   - Los ajustes **CARGO** (a favor) y **DESCARGO** (merma/daño/conteo) exigen una nota
     de justificación obligatoria — el backend rechaza la operación si el campo
     `notes` llega vacío (`MOVEMENTS_REQUIRING_ACTA`).

5. **Auditoría.** Cada movimiento (ENTRADA, SALIDA, TRASLADO, CARGO, DESCARGO) queda
   registrado en la colección `commercial_movements` con usuario, cantidad, almacén,
   lote(s) consumidos y la nota/acta cuando aplica. Las facturas de venta generan
   además un movimiento `SALIDA` referenciado con el número de factura.

6. **Alertas de stock.** Tras cada actualización, el catálogo evalúa visualmente:
   - **Stock en cero** → banner rojo "Sin Stock" + etiqueta roja en la fila del
     producto.
   - **Stock por debajo del mínimo configurado** (`min_stock`) → banner ámbar
     "Mínimo" + etiqueta ámbar en la fila. Cuando se filtra por un almacén específico,
     la validación se hace contra la existencia de **ese** almacén puntual, no el
     total agregado de la empresa.
