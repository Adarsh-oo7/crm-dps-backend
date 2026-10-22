import os
from decimal import Decimal

from django.conf import settings
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

NAVY = HexColor('#070b14')
BLUE = HexColor('#1d6dff')
INK = HexColor('#0f172a')
MUTED = HexColor('#64748b')
LINE = HexColor('#e2e8f0')
PAPER = HexColor('#f8fafc')
BAND = HexColor('#eef4ff')
LOGO = os.path.join(os.path.dirname(__file__), 'assets', 'gaming-hub-logo.jpg')
LEFT = 40
RIGHT = 555


def rupee(amount):
    value = Decimal(amount or 0)
    whole = int(value.quantize(Decimal('1')))
    return f"Rs. {whole:,}"


def long_date(day):
    return f"{day.day} {day.strftime('%B %Y')}"


def generate_rental_pdf(estimate):
    os.makedirs(os.path.join(settings.MEDIA_ROOT, 'rentals'), exist_ok=True)
    filename = f"{estimate.estimate_number}.pdf"
    relative = f"rentals/{filename}"
    path = os.path.join(settings.MEDIA_ROOT, relative)

    width, height = A4
    pdf = canvas.Canvas(path, pagesize=A4)
    pdf.setTitle(f"Rental Estimate - {estimate.customer_name}")
    lines = list(estimate.lines.all())
    subtotal = estimate.subtotal
    advance = estimate.advance_amount
    balance = subtotal - advance
    days = max((int(line.days) for line in lines), default=estimate.days)
    day_word = 'Day' if days == 1 else 'Days'
    prepared = ''
    if estimate.created_by_id:
        prepared = (estimate.created_by.full_name or estimate.created_by.email or '').strip()

    pdf.setFillColor(NAVY)
    pdf.rect(0, height - 126, width, 126, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.rect(0, height - 130, width, 4, fill=1, stroke=0)
    if os.path.exists(LOGO):
        pdf.drawImage(LOGO, 36, height - 112, width=84, height=84)
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(132, height - 52, 'DPS GAMING HUB')
    pdf.setFillColor(BLUE)
    pdf.setFont('Helvetica-Bold', 9)
    pdf.drawString(132, height - 68, 'A Unit of Digital Product Solutions')
    pdf.setFillColor(HexColor('#94a3b8'))
    pdf.setFont('Helvetica', 8)
    pdf.drawString(132, height - 84, 'Korani, Between Attingal & Kazhakkoottam')
    pdf.drawString(132, height - 96, 'Trivandrum')
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawRightString(RIGHT, height - 52, 'RENTAL ESTIMATE')
    pdf.setFillColor(HexColor('#93c5fd'))
    pdf.setFont('Helvetica', 9)
    pdf.drawRightString(RIGHT, height - 70, estimate.estimate_number)
    pdf.drawRightString(RIGHT, height - 84, long_date(estimate.date_issued))

    y = height - 158

    def meta(x, yy, label, value, value_color=INK):
        pdf.setFillColor(MUTED)
        pdf.setFont('Helvetica', 7.5)
        pdf.drawString(x, yy + 11, label.upper())
        pdf.setFillColor(value_color)
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(x, yy, _clip(str(value), 'Helvetica-Bold', 10, 230))

    pdf.setFillColor(PAPER)
    pdf.roundRect(LEFT, y - 62, RIGHT - LEFT, 78, 6, fill=1, stroke=0)
    meta(52, y - 8, 'Customer', estimate.customer_name)
    meta(300, y - 8, 'Status', 'Advance requested', BLUE)
    meta(52, y - 42, 'Delivery', estimate.delivery_location)
    meta(300, y - 42, 'Contact', estimate.phone)

    y -= 86
    pdf.setFillColor(BAND)
    pdf.roundRect(LEFT, y - 28, RIGHT - LEFT, 42, 6, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.roundRect(RIGHT - 78, y - 18, 68, 22, 11, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 9)
    pdf.drawCentredString(RIGHT - 44, y - 11, f'{days} {day_word.upper()}')
    pdf.setFillColor(MUTED)
    pdf.setFont('Helvetica', 7.5)
    pdf.drawString(52, y + 2, 'RENTAL PERIOD  ·  24 HOURS PER DAY')
    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(52, y - 16, f'{long_date(estimate.start_date)}   –   {long_date(estimate.end_date)}')

    y -= 56
    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(LEFT, y, 'Rental items')
    y -= 8
    qty_x, days_x, rate_x, amount_x = 318, 372, 460, RIGHT
    pdf.setFillColor(NAVY)
    pdf.roundRect(LEFT, y - 22, RIGHT - LEFT, 22, 3, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 8)
    pdf.drawString(52, y - 14, 'DESCRIPTION')
    pdf.drawRightString(qty_x, y - 14, 'QTY')
    pdf.drawRightString(days_x, y - 14, 'DAYS')
    pdf.drawRightString(rate_x, y - 14, 'RATE / DAY')
    pdf.drawRightString(amount_x - 12, y - 14, 'AMOUNT')
    y -= 22
    for index, line in enumerate(lines):
        if index % 2 == 0:
            pdf.setFillColor(PAPER)
            pdf.rect(LEFT, y - 24, RIGHT - LEFT, 24, fill=1, stroke=0)
        pdf.setStrokeColor(LINE)
        pdf.setLineWidth(0.4)
        pdf.line(LEFT, y - 24, RIGHT, y - 24)
        pdf.setFillColor(INK)
        pdf.setFont('Helvetica', 9)
        pdf.drawString(52, y - 15, _clip(line.description, 'Helvetica', 9, 220))
        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawRightString(qty_x, y - 15, _qty(line.quantity))
        pdf.drawRightString(days_x, y - 15, str(line.days))
        pdf.setFont('Helvetica', 9)
        pdf.drawRightString(rate_x, y - 15, rupee(line.rate_per_day))
        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawRightString(amount_x - 12, y - 15, rupee(line.amount))
        y -= 24

    y -= 16
    box_top = y
    pdf.setFillColor(PAPER)
    pdf.roundRect(320, y - 62, RIGHT - 320, 70, 6, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.setFont('Helvetica', 9)
    pdf.drawString(332, y - 16, 'Subtotal')
    pdf.drawString(332, y - 34, 'Advance to lock the booking')
    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 9)
    pdf.drawRightString(amount_x - 12, y - 16, rupee(subtotal))
    pdf.drawRightString(amount_x - 12, y - 34, rupee(advance))
    pdf.setStrokeColor(LINE)
    pdf.line(332, y - 42, amount_x - 12, y - 42)
    pdf.setFillColor(BLUE)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(332, y - 56, 'Balance on delivery')
    pdf.drawRightString(amount_x - 12, y - 56, rupee(balance))

    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(LEFT, box_top - 16, 'Pay now')
    pdf.setFillColor(BLUE)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(LEFT, box_top - 38, rupee(advance))
    pdf.setFillColor(MUTED)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(LEFT, box_top - 54, 'UPI, bank transfer, or cash')

    y -= 86
    pdf.setFillColor(NAVY)
    pdf.roundRect(LEFT, y - 32, RIGHT - LEFT, 40, 6, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 8.5)
    span = f'{estimate.start_date.day}–{estimate.end_date.day} {estimate.end_date.strftime("%B %Y")}'
    pdf.drawString(52, y - 8, f'{rupee(advance)} advance confirms this booking for {span}.')
    pdf.setFont('Helvetica', 8)
    pdf.setFillColor(HexColor('#cbd5e1'))
    pdf.drawString(52, y - 22, f'Balance of {rupee(balance)} is payable to the delivery team at drop-off.')

    y -= 56
    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(LEFT, y, 'Terms')
    gear = ', '.join(f'{_qty(line.quantity)} {line.description}' for line in lines) or 'the rented equipment'
    terms = [
        'This estimate is valid for the rental period above and depends on equipment being free.',
        f'A {rupee(advance)} advance locks the booking. The advance is not refundable.',
        f'The balance of {rupee(balance)} is payable by cash or UPI when we deliver.',
        f'We deliver, set up, and collect the equipment at {estimate.delivery_location}.',
        f'The customer is responsible for {gear} during the rental.',
        'Damage, loss, or missing accessories are charged at replacement cost.',
        'A valid ID, and a refundable deposit if we ask for one, is collected on delivery.',
        'Tell us at least 24 hours ahead to change or cancel the dates.',
    ]
    yy = y - 16
    for term in terms:
        wrapped = _wrap(term, RIGHT - LEFT - 16)
        pdf.setFillColor(BLUE)
        pdf.circle(48, yy + 2, 1.6, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont('Helvetica', 8)
        for piece in wrapped:
            pdf.drawString(58, yy, piece)
            yy -= 11
        yy -= 2

    yy -= 8
    pdf.setFillColor(INK)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(LEFT, yy, 'Payment')
    rows = [
        ('Amount', f'{rupee(advance)} booking advance'),
        ('Mode', 'UPI  ·  Bank transfer  ·  Cash'),
        ('Contact', f'{estimate.phone}   ·   {estimate.email}'),
        ('Web', estimate.website),
    ]
    yy -= 18
    for label, value in rows:
        pdf.setFillColor(MUTED)
        pdf.setFont('Helvetica', 8)
        pdf.drawString(LEFT, yy, label)
        pdf.setFillColor(INK)
        pdf.setFont('Helvetica-Bold', 8.5)
        pdf.drawString(110, yy, _clip(value, 'Helvetica-Bold', 8.5, RIGHT - 110))
        yy -= 14

    pdf.setFillColor(NAVY)
    pdf.rect(0, 0, width, 36, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.rect(0, 36, width, 3, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Oblique', 8)
    pdf.drawString(LEFT, 15, 'Thank you for choosing DPS Gaming Hub')
    if prepared:
        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawRightString(RIGHT, 15, f'By {prepared}')

    pdf.save()
    estimate.pdf_file.name = relative
    estimate.save(update_fields=['pdf_file'])
    return f"{settings.MEDIA_URL}{relative}"


def _clip(text, font, size, limit):
    if pdfmetrics.stringWidth(text, font, size) <= limit:
        return text
    trimmed = text
    while trimmed and pdfmetrics.stringWidth(trimmed + '…', font, size) > limit:
        trimmed = trimmed[:-1]
    return (trimmed or text[:1]) + '…'


def _qty(value):
    number = Decimal(value)
    if number == number.to_integral():
        return str(int(number))
    return str(number)


def _wrap(text, limit):
    words = text.split()
    lines = []
    current = ''
    for word in words:
        trial = f'{current} {word}'.strip()
        if pdfmetrics.stringWidth(trial, 'Helvetica', 8) <= limit:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or ['']
