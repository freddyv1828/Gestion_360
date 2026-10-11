from datetime import datetime
from bson import ObjectId
from database import get_company_db

# Tramos de comisión por velocidad de cobro, contados desde la ENTREGA
# confirmada (invoice.delivered_at) hasta el momento en que el dinero
# efectivamente entra (el abono, o la propia factura si se cobró de
# contado/transferencia/tarjeta al momento de facturar).
COMMISSION_TIERS = [
    (0, 7, 4.0),
    (8, 15, 2.0),
    (16, 21, 1.0),
]
COMMISSION_DEFAULT_RATE = 0.0  # 22 días en adelante: no genera comisión.


def get_commission_rate(days_elapsed):
    """None si no se puede determinar (sin fecha de entrega todavía).

    Un `days_elapsed` negativo (el cobro quedó registrado antes que la
    entrega — típico de Contado, donde se cobra al instante y la entrega
    física puede sellarse después vía una hoja de despacho) se trata como 0:
    cobrar antes o al momento de entregar es, por definición, la cobranza
    más rápida posible, así que merece el tramo más alto, no una penalidad
    por una resta que dio negativa."""
    if days_elapsed is None:
        return None
    days_elapsed = max(days_elapsed, 0)
    for lo, hi, rate in COMMISSION_TIERS:
        if lo <= days_elapsed <= hi:
            return rate
    return COMMISSION_DEFAULT_RATE


class CommissionService:
    """
    Comisión de vendedores por velocidad de cobro. No es un porcentaje sobre
    lo facturado: es sobre lo efectivamente COBRADO, y el reloj arranca en la
    entrega confirmada (InvoicingService.mark_delivered), no en la fecha de
    la factura — una factura que tardó un mes en despacharse no debe
    penalizar al vendedor por algo que no dependía de él.

    Dos tipos de "evento de cobro":
      - Abono (ar_payments) sobre una factura a Crédito.
      - La propia factura, si se pagó de Contado/Transferencia/Tarjeta al
        momento de facturar (ahí no se genera ar_payments; la cobranza es
        instantánea).
    """

    @staticmethod
    def get_commission_events(company_db_name, filters=None):
        db = get_company_db(company_db_name)
        if db is None:
            return []
        filters = filters or {}

        seller_filter = (filters.get('seller') or '').strip()
        route_filter_raw = (filters.get('route_number') or '').strip()
        route_filter = None
        if route_filter_raw:
            try:
                route_filter = int(route_filter_raw)
            except ValueError:
                route_filter = None

        date_query = {}
        date_from = (filters.get('date_from') or '').strip()
        date_to = (filters.get('date_to') or '').strip()
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

        events = []

        # --- Abonos sobre facturas a Crédito ---
        payment_query = {}
        if seller_filter:
            payment_query['seller'] = seller_filter
        if date_query:
            payment_query['created_at'] = date_query
        payments = list(db['ar_payments'].find(payment_query))

        invoice_ids = list({p['invoice_id'] for p in payments if p.get('invoice_id')})
        invoices_by_id = {}
        if invoice_ids:
            for inv in db['invoices'].find({"_id": {"$in": invoice_ids}}, {"delivered_at": 1, "route_number": 1, "invoice_number": 1}):
                invoices_by_id[inv['_id']] = inv

        for p in payments:
            invoice = invoices_by_id.get(p.get('invoice_id'), {})
            route_number = invoice.get('route_number')
            if route_filter is not None and route_number != route_filter:
                continue
            delivered_at = invoice.get('delivered_at')
            collected_at = p.get('created_at')
            days_elapsed = (collected_at - delivered_at).days if (delivered_at and collected_at) else None
            rate = get_commission_rate(days_elapsed)
            amount_usd = p.get('amount_usd')
            events.append({
                "type": "abono",
                "invoice_id": str(p['invoice_id']) if p.get('invoice_id') else None,
                "invoice_number": p.get('invoice_number') or invoice.get('invoice_number'),
                "client_name": p.get('client_name'),
                "seller": p.get('seller'),
                "route_number": route_number,
                "collected_at": collected_at,
                "delivered_at": delivered_at,
                "days_elapsed": days_elapsed,
                "amount_usd": amount_usd,
                "commission_rate": rate,
                "commission_usd": round(amount_usd * rate / 100.0, 2) if (amount_usd is not None and rate is not None) else None,
            })

        # --- Facturas cobradas de inmediato (Contado / Transferencia / Tarjeta) ---
        invoice_query = {"status": "emitida", "payment_method": {"$ne": "Crédito"}}
        if seller_filter:
            invoice_query['seller'] = seller_filter
        if route_filter is not None:
            invoice_query['route_number'] = route_filter
        if date_query:
            invoice_query['created_at'] = date_query
        cash_invoices = list(db['invoices'].find(invoice_query))

        for inv in cash_invoices:
            delivered_at = inv.get('delivered_at')
            collected_at = inv.get('created_at')
            days_elapsed = (collected_at - delivered_at).days if (delivered_at and collected_at) else None
            rate = get_commission_rate(days_elapsed)
            amount_usd = inv.get('total_usd')
            events.append({
                "type": "contado",
                "invoice_id": str(inv['_id']),
                "invoice_number": inv.get('invoice_number'),
                "client_name": inv.get('client_name'),
                "seller": inv.get('seller'),
                "route_number": inv.get('route_number'),
                "collected_at": collected_at,
                "delivered_at": delivered_at,
                "days_elapsed": days_elapsed,
                "amount_usd": amount_usd,
                "commission_rate": rate,
                "commission_usd": round(amount_usd * rate / 100.0, 2) if (amount_usd is not None and rate is not None) else None,
            })

        events.sort(key=lambda e: e['collected_at'] or datetime.min, reverse=True)
        return events

    @staticmethod
    def get_commission_summary(company_db_name, filters=None):
        """Agrupado por vendedor: total cobrado, comisión ganada, y dos
        contadores de "todavía no calculable" que NO deben mezclarse —
        causas distintas con remedios distintos:
          - pending_delivery_count: sin `delivered_at` todavía (falta
            confirmar la entrega — ver InvoicingService.mark_delivered).
          - pending_fx_count: la entrega SÍ está confirmada y la tasa ya se
            calculó, pero el abono no tiene `amount_usd` (sin tasa de cambio
            vigente para convertir su moneda) — falta configurar la tasa,
            no falta entregar nada.
        """
        events = CommissionService.get_commission_events(company_db_name, filters=filters)
        by_seller = {}
        for e in events:
            seller = e.get('seller') or 'Sin vendedor'
            bucket = by_seller.setdefault(seller, {
                "seller": seller, "event_count": 0,
                "pending_delivery_count": 0, "pending_fx_count": 0,
                "total_collected_usd": 0.0, "total_commission_usd": 0.0,
            })
            bucket['event_count'] += 1
            if e['commission_usd'] is None:
                if e['commission_rate'] is None:
                    bucket['pending_delivery_count'] += 1
                else:
                    bucket['pending_fx_count'] += 1
            else:
                bucket['total_commission_usd'] += e['commission_usd']
            if e['amount_usd'] is not None:
                bucket['total_collected_usd'] += e['amount_usd']

        for b in by_seller.values():
            b['total_collected_usd'] = round(b['total_collected_usd'], 2)
            b['total_commission_usd'] = round(b['total_commission_usd'], 2)

        summary = sorted(by_seller.values(), key=lambda b: (b['total_commission_usd'], b['total_collected_usd']), reverse=True)
        return {
            "by_seller": summary,
            "total_commission_usd": round(sum(b['total_commission_usd'] for b in summary), 2),
            "total_collected_usd": round(sum(b['total_collected_usd'] for b in summary), 2),
            "events": events,
        }
