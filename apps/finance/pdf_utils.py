import os
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_for_invoice(invoice):
    filename = f"invoice_{invoice.invoice_number}.pdf"
    os.makedirs(os.path.join(settings.MEDIA_ROOT, 'finance'), exist_ok=True)
    filepath = os.path.join(settings.MEDIA_ROOT, 'finance', filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#4F46E5') # Indigo
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E1B4B')
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#374151')
    )

    story.append(Paragraph("DIGITAL PRODUCT SOLUTIONS (DPS)", header_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"INVOICE {invoice.invoice_number}", title_style))
    story.append(Spacer(1, 15))

    meta_data = [
        [Paragraph("<b>From:</b><br/>Digital Product Solutions<br/>sales@digitalprod.com", body_style),
         Paragraph(f"<b>To:</b><br/>{invoice.client.company_name}<br/>{invoice.client.website or ''}", body_style)],
        [Paragraph(f"<b>Invoice Date:</b> {invoice.invoice_date}", body_style),
         Paragraph(f"<b>Due Date:</b> {invoice.due_date}", body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    table_data = [[
        Paragraph("<b>Description</b>", header_style),
        Paragraph("<b>Quantity</b>", header_style),
        Paragraph("<b>Unit Price</b>", header_style),
        Paragraph("<b>Tax %</b>", header_style),
        Paragraph("<b>Discount %</b>", header_style),
        Paragraph("<b>Total</b>", header_style),
    ]]

    for item in invoice.line_items.all():
        table_data.append([
            Paragraph(item.description, body_style),
            Paragraph(str(item.quantity), body_style),
            Paragraph(f"${item.unit_price}", body_style),
            Paragraph(f"{item.tax_percent}%", body_style),
            Paragraph(f"{item.discount_percent}%", body_style),
            Paragraph(f"${item.total}", body_style),
        ])

    items_table = Table(table_data, colWidths=[200, 60, 70, 50, 60, 100])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EEF2FF')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    summary_data = [
        ["", Paragraph("<b>Subtotal:</b>", body_style), f"${invoice.subtotal}"],
        ["", Paragraph("<b>Discount:</b>", body_style), f"-${invoice.discount_amount}"],
        ["", Paragraph("<b>Tax:</b>", body_style), f"${invoice.tax_amount}"],
        ["", Paragraph("<b>Grand Total:</b>", header_style), f"${invoice.total_amount}"],
    ]
    summary_table = Table(summary_data, colWidths=[340, 100, 100])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    if invoice.terms_and_conditions:
        story.append(Paragraph("<b>Terms & Conditions:</b>", header_style))
        story.append(Spacer(1, 5))
        story.append(Paragraph(invoice.terms_and_conditions, body_style))

    doc.build(story)
    
    # Save the relative file path to the FileField
    relative_path = f"finance/{filename}"
    invoice.pdf_file.name = relative_path
    invoice.save(update_fields=['pdf_file'])
    return f"{settings.MEDIA_URL}{relative_path}"


def generate_pdf_for_proposal(proposal):
    filename = f"proposal_{proposal.proposal_number}.pdf"
    os.makedirs(os.path.join(settings.MEDIA_ROOT, 'finance'), exist_ok=True)
    filepath = os.path.join(settings.MEDIA_ROOT, 'finance', filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ProposalTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#4F46E5')
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E1B4B')
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#374151')
    )

    story.append(Paragraph("DIGITAL PRODUCT SOLUTIONS (DPS)", header_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"PROPOSAL: {proposal.project_name}", title_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"Proposal ID: {proposal.proposal_number}", body_style))
    story.append(Spacer(1, 15))

    meta_data = [
        [Paragraph(f"<b>For Client:</b><br/>{proposal.client.company_name}<br/>{proposal.client.website or ''}", body_style),
         Paragraph(f"<b>Valid Until:</b> {proposal.valid_until}<br/><b>Status:</b> {proposal.status}", body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Scope of Work:</b>", header_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(proposal.description, body_style))
    story.append(Spacer(1, 20))

    # Items table
    table_data = [[
        Paragraph("<b>Description</b>", header_style),
        Paragraph("<b>Qty</b>", header_style),
        Paragraph("<b>Unit Price</b>", header_style),
        Paragraph("<b>Total</b>", header_style),
    ]]

    grand_total = 0
    for item in proposal.line_items.all():
        table_data.append([
            Paragraph(item.description, body_style),
            Paragraph(str(item.quantity), body_style),
            Paragraph(f"${item.unit_price}", body_style),
            Paragraph(f"${item.total}", body_style),
        ])
        grand_total += item.total

    items_table = Table(table_data, colWidths=[280, 50, 90, 120])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EEF2FF')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    # Totals
    summary_data = [
        ["", Paragraph("<b>Estimated Total Cost:</b>", header_style), f"${grand_total}"]
    ]
    summary_table = Table(summary_data, colWidths=[320, 120, 100])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    if proposal.notes:
        story.append(Paragraph("<b>Additional Notes:</b>", header_style))
        story.append(Spacer(1, 5))
        story.append(Paragraph(proposal.notes, body_style))

    doc.build(story)
    
    relative_path = f"finance/{filename}"
    proposal.pdf_file.name = relative_path
    proposal.save(update_fields=['pdf_file'])
    return f"{settings.MEDIA_URL}{relative_path}"


def generate_pdf_for_quotation(quotation):
    filename = f"quotation_{quotation.quotation_number}.pdf"
    os.makedirs(os.path.join(settings.MEDIA_ROOT, 'finance'), exist_ok=True)
    filepath = os.path.join(settings.MEDIA_ROOT, 'finance', filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'QuoTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#4F46E5')
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E1B4B')
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#374151')
    )

    story.append(Paragraph("DIGITAL PRODUCT SOLUTIONS (DPS)", header_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"QUOTATION {quotation.quotation_number}", title_style))
    story.append(Spacer(1, 15))

    target_name = quotation.client.company_name if quotation.client else (quotation.lead.company_name if quotation.lead else "Valued Lead")
    meta_data = [
        [Paragraph(f"<b>For:</b> {target_name}", body_style),
         Paragraph(f"<b>Valid Until:</b> {quotation.valid_until}<br/><b>Status:</b> {quotation.status}", body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Project Summary:</b>", header_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(quotation.project_description, body_style))
    story.append(Spacer(1, 20))

    # Items table
    table_data = [[
        Paragraph("<b>Description</b>", header_style),
        Paragraph("<b>Qty</b>", header_style),
        Paragraph("<b>Unit Price</b>", header_style),
        Paragraph("<b>Total</b>", header_style),
    ]]

    grand_total = 0
    for item in quotation.line_items.all():
        table_data.append([
            Paragraph(item.description, body_style),
            Paragraph(str(item.quantity), body_style),
            Paragraph(f"${item.unit_price}", body_style),
            Paragraph(f"${item.total}", body_style),
        ])
        grand_total += item.total

    items_table = Table(table_data, colWidths=[280, 50, 90, 120])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EEF2FF')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    summary_data = [
        ["", Paragraph("<b>Quotation Total:</b>", header_style), f"${grand_total}"]
    ]
    summary_table = Table(summary_data, colWidths=[320, 120, 100])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    if quotation.notes:
        story.append(Paragraph("<b>Notes:</b>", header_style))
        story.append(Spacer(1, 5))
        story.append(Paragraph(quotation.notes, body_style))

    doc.build(story)
    
    relative_path = f"finance/{filename}"
    quotation.pdf_file.name = relative_path
    quotation.save(update_fields=['pdf_file'])
    return f"{settings.MEDIA_URL}{relative_path}"
