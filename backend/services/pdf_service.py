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

    table_data = [["Artículo", "SKU", "Cant.", "Precio Unit.", "IVA", "Total"]]
    for item in invoice.get('items', []):
        table_data.append([
            item.get('name', ''), item.get('sku', ''), str(item.get('quantity', '')),
            f"${item.get('unit_price', 0):.2f}", f"{item.get('iva_rate', 0)}%", f"${item.get('total', 0):.2f}"
        ])

    items_table = Table(table_data, colWidths=[6 * cm, 2.5 * cm, 1.5 * cm, 2.5 * cm, 1.5 * cm, 2.5 * cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.4 * cm))

    totals_data = [["Subtotal", f"${invoice.get('subtotal_usd', invoice.get('subtotal', 0)):.2f}"]]
    if invoice.get('discount_amount_usd'):
        label = "Descuento"
        if invoice.get('coupon_code'):
            label += f" (Cupón {invoice['coupon_code']})"
        totals_data.append([label, f"-${invoice['discount_amount_usd']:.2f}"])
    iva_label = "IVA (No aplica)" if invoice.get('doc_type') == 'nota_entrega' else "IVA"
    totals_data.append([iva_label, f"${invoice.get('iva_total_usd', invoice.get('iva_total', 0)):.2f}"])
    totals_data.append([f"TOTAL ({invoice.get('currency', 'USD')})", f"{invoice.get('total', 0):.2f} {invoice.get('currency', 'USD')}"])

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
