from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

BRAND_COLOR = colors.HexColor('#4f46e5')
DARK_COLOR = colors.HexColor('#0f172a')


def _base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Title2', parent=styles['Heading1'], fontSize=16, textColor=DARK_COLOR))
    styles.add(ParagraphStyle(name='Small', parent=styles['Normal'], fontSize=8, textColor=colors.grey))
    styles.add(ParagraphStyle(name='SmallRight', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='RightBold', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT))
    return styles


def generate_table_pdf(title, company_name, headers, rows, subtitle=None, col_widths=None, landscape_mode=True):
    """
    Genera un PDF tabular genérico (listados de Productos/Almacén, Clientes,
    Pedidos, Compras, etc.) a partir de encabezados y filas ya resueltas a texto.
    `rows`: lista de listas de strings (mismo orden que `headers`). Retorna bytes.
    """
    from reportlab.lib.pagesizes import landscape as _landscape

    buffer = BytesIO()
    pagesize = _landscape(letter) if landscape_mode else letter
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    styles = _base_styles()
    elements = []

    elements.append(Paragraph(f"<b>{company_name}</b>", styles['Normal']))
    elements.append(Paragraph(f"<font size=14><b>{title}</b></font>", styles['Title2']))
    if subtitle:
        elements.append(Paragraph(subtitle, styles['Small']))
    elements.append(Spacer(1, 0.4 * cm))

    table_data = [headers] + rows
    page_width = pagesize[0] - 3 * cm
    if not col_widths:
        col_widths = [page_width / len(headers)] * len(headers)
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"<font size=8 color=grey>Total de registros: {len(rows)}</font>", styles['Small']))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_invoice_pdf(invoice, company_name, company_rif):
    """Genera el PDF formal de una Factura Fiscal o Nota de Entrega. Retorna bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _base_styles()
    elements = []

    doc_label = "NOTA DE ENTREGA" if invoice.get('doc_type') == 'nota_entrega' else "FACTURA"
    header_table = Table([
        [Paragraph(f"<b>{company_name}</b><br/>{company_rif}", styles['Normal']),
         Paragraph(f"<b>{doc_label}</b><br/>N° {invoice.get('invoice_number', '')}", styles['SmallRight'])]
    ], colWidths=[10 * cm, 7 * cm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"<para borderWidth=0 borderColor=white><font size=9>Fecha: {invoice.get('created_at').strftime('%Y-%m-%d %H:%M') if invoice.get('created_at') else ''} &nbsp;&nbsp; Estado: {invoice.get('status', '').upper()}</font></para>", styles['Normal']))
    elements.append(Spacer(1, 0.4 * cm))

    client_info = (
        f"<b>Cliente:</b> {invoice.get('client_name', '')}<br/>"
        f"<b>RIF/Cédula:</b> {invoice.get('client_rif', '')}<br/>"
        f"<b>Vendedor:</b> {invoice.get('seller') or invoice.get('user', '')}<br/>"
        f"<b>Método de Pago:</b> {invoice.get('payment_method', '')}"
    )
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 0.5 * cm))

    currency = invoice.get('currency', 'USD')
    exchange_rate = invoice.get('exchange_rate_used')

    def _to_invoice_currency(amount_usd):
        """Los items se guardan siempre en USD (precio de catálogo); si la
        factura se emitió en otra moneda, hay que convertirlos con la misma
        tasa ya usada para el total, para no mezclar $ (USD) con el total en
        VES/EUR/COP."""
        if currency != 'USD' and exchange_rate:
            return float(amount_usd) * exchange_rate
        return float(amount_usd)

    # Nota: el precio de catálogo YA incluye IVA (es el precio al público), por
    # eso "Precio Unit." se muestra con IVA — pero la columna de línea muestra
    # el SUBTOTAL sin IVA de esa línea, para que sumando esta columna dé
    # exactamente el "Subtotal Bruto" de más abajo (antes, esta columna decía
    # "Total" y mostraba el monto CON IVA, que no tenía relación aritmética
    # visible con el "Subtotal" del resumen, y la factura "no cuadraba").
    table_data = [["Artículo", "SKU", "Cant.", f"P. Unit. c/IVA ({currency})", "IVA", f"Subtotal s/IVA ({currency})"]]
    for item in invoice.get('items', []):
        table_data.append([
            item.get('name', ''), item.get('sku', ''), str(item.get('quantity', '')),
            f"{_to_invoice_currency(item.get('unit_price', 0)):.2f}", f"{item.get('iva_rate', 0)}%",
            f"{_to_invoice_currency(item.get('subtotal', 0)):.2f}"
        ])

    items_table = Table(table_data, colWidths=[4.5 * cm, 2 * cm, 1.2 * cm, 3 * cm, 1.3 * cm, 3 * cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.4 * cm))

    # discount_amount/subtotal_before_discount ya vienen convertidos a la
    # moneda de la factura desde invoicing_service.py; para facturas viejas
    # (previas a este campo) se reconstruyen a partir de lo que sí existía.
    discount_final = invoice.get('discount_amount')
    if discount_final is None:
        discount_final = _to_invoice_currency(invoice.get('discount_amount_usd', 0))
    subtotal_bruto_final = invoice.get('subtotal_before_discount')
    if subtotal_bruto_final is None:
        subtotal_bruto_final = invoice.get('subtotal', 0) + discount_final

    totals_data = [[f"Subtotal Bruto ({currency})", f"{subtotal_bruto_final:.2f}"]]
    if discount_final:
        label = "Descuento"
        if invoice.get('coupon_code'):
            label += f" (Cupón {invoice['coupon_code']})"
        totals_data.append([label, f"-{discount_final:.2f}"])
    totals_data.append([f"Subtotal Neto ({currency})", f"{invoice.get('subtotal', 0):.2f}"])
    iva_label = "IVA (No aplica)" if invoice.get('doc_type') == 'nota_entrega' else "IVA"
    totals_data.append([iva_label, f"{invoice.get('iva_total', 0):.2f}"])
    totals_data.append([f"TOTAL ({currency})", f"{invoice.get('total', 0):.2f} {currency}"])

    totals_table = Table(totals_data, colWidths=[4 * cm, 4 * cm], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, DARK_COLOR),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)

    if invoice.get('notes'):
        elements.append(Spacer(1, 0.6 * cm))
        elements.append(Paragraph(f"<b>Notas:</b> {invoice['notes']}", styles['Small']))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_commission_receipt_pdf(company_name, company_rif, seller_name, period_label, events, total_commission_usd, total_collected_usd):
    """
    Recibo formal de comisión para UN vendedor y un período: detalle de cada
    cobro que generó comisión (factura, cliente, fecha de entrega, fecha de
    cobro, días transcurridos, tasa aplicada y monto), con el total al pie y
    una línea de firma — pensado para imprimir y entregarle al vendedor como
    constancia de lo que se le está pagando, no solo para uso interno.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _base_styles()
    elements = []

    header_table = Table([
        [Paragraph(f"<b>{company_name}</b><br/>{company_rif}", styles['Normal']),
         Paragraph("<b>RECIBO DE COMISIÓN</b>", styles['SmallRight'])]
    ], colWidths=[10 * cm, 7 * cm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * cm))

    info = (
        f"<b>Vendedor:</b> {seller_name}<br/>"
        f"<b>Período:</b> {period_label}<br/>"
        f"<b>Cobros que generaron comisión:</b> {len(events)}"
    )
    elements.append(Paragraph(info, styles['Normal']))
    elements.append(Spacer(1, 0.5 * cm))

    table_data = [["Factura", "Cliente", "Entregado", "Cobrado", "Días", "Tasa", "Cobrado USD", "Comisión USD"]]
    for e in events:
        table_data.append([
            e.get('invoice_number', ''),
            (e.get('client_name') or '')[:28],
            e['delivered_at'].strftime('%Y-%m-%d') if e.get('delivered_at') else '—',
            e['collected_at'].strftime('%Y-%m-%d') if e.get('collected_at') else '—',
            str(e['days_elapsed']) if e.get('days_elapsed') is not None else '—',
            f"{e['commission_rate']}%" if e.get('commission_rate') is not None else '—',
            f"{e['amount_usd']:.2f}" if e.get('amount_usd') is not None else '—',
            f"{e['commission_usd']:.2f}" if e.get('commission_usd') is not None else '—',
        ])

    items_table = Table(table_data, colWidths=[2.3 * cm, 3.8 * cm, 2 * cm, 2 * cm, 1.3 * cm, 1.4 * cm, 2.2 * cm, 2.2 * cm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.4 * cm))

    totals_data = [
        [f"Total Cobrado (USD)", f"{total_collected_usd:.2f}"],
        [f"TOTAL COMISIÓN (USD)", f"{total_commission_usd:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[5 * cm, 4 * cm], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, DARK_COLOR),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)

    elements.append(Spacer(1, 1.5 * cm))
    signature_table = Table([
        ["_" * 35, "_" * 35],
        ["Firma del vendedor (recibido conforme)", "Firma de administración"],
    ], colWidths=[8 * cm, 8 * cm])
    signature_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.grey),
    ]))
    elements.append(signature_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_dispatch_guide_pdf(invoice, company_name, company_rif, route_info=None):
    """Genera la Guía de Despacho (packing list) de una factura: items y cantidades
    SIN precios, orientado a transporte/entrega física. Retorna bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _base_styles()
    elements = []

    header_table = Table([
        [Paragraph(f"<b>{company_name}</b><br/>{company_rif}", styles['Normal']),
         Paragraph(f"<b>GUÍA DE DESPACHO</b><br/>Ref. Factura {invoice.get('invoice_number', '')}", styles['SmallRight'])]
    ], colWidths=[10 * cm, 7 * cm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.4 * cm))

    dest_info = (
        f"<b>Cliente / Destinatario:</b> {invoice.get('client_name', '')}<br/>"
        f"<b>RIF/Cédula:</b> {invoice.get('client_rif', '')}<br/>"
    )
    if route_info:
        dest_info += (
            f"<b>Vehículo:</b> {route_info.get('vehicle_plate', 'N/D')} &nbsp;&nbsp; "
            f"<b>Chofer:</b> {route_info.get('driver_name', 'N/D')} &nbsp;&nbsp; "
            f"<b>Ruta:</b> {route_info.get('route_code', 'N/D')}"
        )
    else:
        dest_info += "<b>Transporte:</b> Sin vehículo/ruta asignado todavía."
    elements.append(Paragraph(dest_info, styles['Normal']))
    elements.append(Spacer(1, 0.5 * cm))

    table_data = [["Artículo", "SKU", "Cantidad", "Unidad", "Peso Aprox. (kg)"]]
    total_weight = 0.0
    for item in invoice.get('items', []):
        qty = float(item.get('quantity', 0))
        unit_weight = float(item.get('weight_kg', 0) or 0)
        line_weight = qty * unit_weight
        total_weight += line_weight
        table_data.append([
            item.get('name', ''), item.get('sku', ''), str(qty), item.get('unit_type', 'unidad'),
            f"{line_weight:.2f}" if unit_weight else "N/D"
        ])

    items_table = Table(table_data, colWidths=[7 * cm, 3 * cm, 2 * cm, 2.5 * cm, 2.5 * cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d97706')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fffbeb')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * cm))
    if total_weight > 0:
        elements.append(Paragraph(f"<b>Peso total estimado:</b> {total_weight:.2f} kg", styles['Normal']))

    elements.append(Spacer(1, 1.2 * cm))
    sign_table = Table([
        ["____________________________", "____________________________"],
        ["Entregado por (Almacén)", "Recibido Conforme (Cliente)"],
    ], colWidths=[8 * cm, 8 * cm])
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.grey),
    ]))
    elements.append(sign_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
