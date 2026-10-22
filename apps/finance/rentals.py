from datetime import date
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone

from apps.clients.models import Client
from apps.projects.models import Project

from .models import Expense, GearItem, Invoice, InvoiceLineItem, Payment, RentalEstimate, RentalLine
from .rental_pdf import generate_rental_pdf

HUB_NAME = 'DPS Gaming Hub'
HUB_LOCK = 7310021


def _hub_lock():
    # Pages fire several finance requests at once; serialise hub setup so they cannot each create a copy.
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [HUB_LOCK])


def _client_named(name, defaults):
    client = Client.objects.filter(company_name=name).order_by('id').first()
    if client:
        return client
    return Client.objects.create(company_name=name, **defaults)


@transaction.atomic
def ensure_gaming_hub(user=None):
    _hub_lock()
    project = Project.objects.filter(name=HUB_NAME).order_by('id').first()
    if project is None:
        project = _create_hub(user)
    if project.currency != 'INR':
        project.currency = 'INR'
        project.save(update_fields=['currency'])
    _ensure_gear(project)
    return project


def _create_hub(user):
    client = _client_named(
        HUB_NAME,
        {
            'industry': 'Equipment rental',
            'website': 'https://gaming.digitalproductsolutions.in',
            'city': 'Trivandrum',
            'state': 'Kerala',
            'country': 'India',
            'client_type': 'Product Client',
            'notes': 'In-house rental unit. 3 PS5 consoles, 3 TVs, and a UPS.',
        },
    )
    return Project.objects.create(
        name=HUB_NAME,
        client=client,
        project_type='In-house Product',
        status='Development',
        currency='INR',
        description='PS5 and TV rentals. Income from bookings, and purchases of gear, stay on this project.',
        live_url='https://gaming.digitalproductsolutions.in',
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def _ensure_gear(project):
    catalog = [
        ('PS5', 'PS5 Console (DualSense included)', 3, Decimal('1000'), 'Console with one controller'),
        ('CONTROLLER', 'Extra DualSense Controller', 3, Decimal('150'), 'Additional wireless DualSense controller'),
        ('TV', 'TV / Monitor', 3, Decimal('0'), 'Set the daily rate when you price the screens'),
        ('UPS', 'UPS 1250v', 1, Decimal('150'), 'Backup power for the console'),
    ]
    have = set(project.gear.values_list('kind', flat=True))
    for kind, name, quantity, rate, notes in catalog:
        if kind not in have:
            GearItem.objects.create(project=project, kind=kind, name=name, quantity=quantity, daily_rate=rate, notes=notes)


def _days(start, end):
    # A booking runs in 24-hour blocks. 22 Oct to 23 Oct is 1 day, not 2.
    span = (end - start).days
    return span if span >= 1 else 1


def _next_number(issued):
    year = issued.year
    prefix = f'DPS-GH-{year}-'
    latest = (
        RentalEstimate.objects.filter(estimate_number__startswith=prefix)
        .order_by('-estimate_number')
        .values_list('estimate_number', flat=True)
        .first()
    )
    seq = 1000
    if latest:
        try:
            seq = int(latest.rsplit('-', 1)[-1])
        except ValueError:
            seq = RentalEstimate.objects.filter(estimate_number__startswith=prefix).count() + 1000
    return f'{prefix}{seq + 1}'


@transaction.atomic
def create_rental(user, payload):
    project = ensure_gaming_hub(user)
    issued = _as_date(payload.get('date_issued')) or timezone.localdate()
    start = _as_date(payload.get('start_date'))
    end = _as_date(payload.get('end_date'))
    if not start or not end or end < start:
        raise ValueError('Choose a rental start and end date.')
    customer = (payload.get('customer_name') or '').strip()
    location = (payload.get('delivery_location') or '').strip()
    if not customer or not location:
        raise ValueError('Customer name and delivery location are required.')
    raw_lines = payload.get('lines') or []
    if not raw_lines:
        raise ValueError('Add at least one rental item.')
    days = _days(start, end)
    number = (payload.get('estimate_number') or '').strip() or _next_number(issued)
    customer_client = _client_named(customer, {'client_type': 'Service Client', 'city': location[:100]})
    estimate = RentalEstimate.objects.create(
        estimate_number=number,
        customer_name=customer,
        project=project,
        client=customer_client,
        date_issued=issued,
        delivery_location=location,
        start_date=start,
        end_date=end,
        advance_amount=Decimal(str(payload.get('advance_amount') or 500)),
        phone=payload.get('phone') or '+91 94003 55185',
        email=payload.get('email') or 'digitalproductkerala@gmail.com',
        website=payload.get('website') or 'gaming.digitalproductsolutions.in',
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    for index, row in enumerate(raw_lines):
        RentalLine.objects.create(
            estimate=estimate,
            description=(row.get('description') or 'Rental item').strip(),
            quantity=Decimal(str(row.get('quantity') or 1)),
            days=days,
            rate_per_day=Decimal(str(row.get('rate_per_day') or 0)),
            order=index,
        )
    invoice = Invoice.objects.create(
        client=customer_client,
        project=project,
        invoice_date=issued,
        due_date=start,
        status='Sent',
        currency='INR',
        notes=f'Rental estimate {estimate.estimate_number}',
        created_by=user if getattr(user, 'is_authenticated', False) else customer_client.account_manager or user,
    )
    if invoice.created_by_id is None and getattr(user, 'is_authenticated', False):
        invoice.created_by = user
        invoice.save(update_fields=['created_by'])
    for line in estimate.lines.all():
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=f"{line.description} ({line.days} days)",
            quantity=line.quantity * line.days,
            unit_price=line.rate_per_day,
            order=line.order,
        )
    invoice.recalculate_totals()
    estimate.invoice = invoice
    estimate.save(update_fields=['invoice'])
    generate_rental_pdf(estimate)
    return estimate


@transaction.atomic
def collect_money(user, payload):
    amount = Decimal(str(payload.get('amount') or 0))
    if amount <= 0:
        raise ValueError('Enter the amount you collected.')
    method = (payload.get('payment_method') or 'UPI').strip()
    notes = (payload.get('notes') or '').strip()
    estimate = None
    if payload.get('estimate'):
        estimate = RentalEstimate.objects.select_related('invoice').filter(pk=payload['estimate']).first()
    invoice = estimate.invoice if estimate else None
    if invoice is None:
        project = ensure_gaming_hub(user)
        if payload.get('project'):
            project = Project.objects.filter(pk=payload['project']).first() or project
        name = (payload.get('customer_name') or 'Cash collection').strip()
        client = _client_named(name, {'client_type': 'Service Client'})
        today = timezone.localdate()
        invoice = Invoice.objects.create(
            client=client,
            project=project,
            invoice_date=today,
            due_date=today,
            status='Sent',
            currency='INR',
            notes=notes or 'Money collected for the company',
            created_by=user,
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=notes or f'Money collected — {project.name}',
            quantity=1,
            unit_price=amount,
        )
        invoice.recalculate_totals()
    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        payment_method=method,
        notes=notes,
        recorded_by=user,
    )
    if estimate and invoice.status == 'Paid':
        estimate.status = 'Closed'
        estimate.save(update_fields=['status'])
    elif estimate and invoice.status == 'Partially Paid' and estimate.status == 'Advance requested':
        estimate.status = 'Confirmed'
        estimate.save(update_fields=['status'])
    return payment


def rental_payload(estimate):
    paid = 0
    if estimate.invoice_id:
        paid = sum(payment.amount for payment in estimate.invoice.payments.all())
    subtotal = estimate.subtotal
    return {
        'id': estimate.id,
        'estimate_number': estimate.estimate_number,
        'customer_name': estimate.customer_name,
        'project': estimate.project_id,
        'project_name': estimate.project.name if estimate.project_id else '',
        'date_issued': estimate.date_issued,
        'status': estimate.status,
        'delivery_location': estimate.delivery_location,
        'start_date': estimate.start_date,
        'end_date': estimate.end_date,
        'days': estimate.days,
        'advance_amount': estimate.advance_amount,
        'subtotal': subtotal,
        'balance': subtotal - estimate.advance_amount,
        'collected': paid,
        'phone': estimate.phone,
        'email': estimate.email,
        'pdf_file': estimate.pdf_file.url if estimate.pdf_file else '',
        'invoice': estimate.invoice_id,
        'invoice_number': estimate.invoice.invoice_number if estimate.invoice_id else '',
        'created_by_name': (
            estimate.created_by.full_name or estimate.created_by.email
            if estimate.created_by_id else ''
        ),
        'lines': [
            {
                'id': line.id,
                'description': line.description,
                'quantity': line.quantity,
                'days': line.days,
                'rate_per_day': line.rate_per_day,
                'amount': line.amount,
            }
            for line in estimate.lines.all()
        ],
    }


def project_money_rows():
    rows = []
    for project in Project.objects.all().order_by('name'):
        invoices = Invoice.objects.filter(project=project).exclude(status='Cancelled')
        invoiced = sum((invoice.total_amount for invoice in invoices), 0)
        collected = sum(
            (payment.amount for payment in Payment.objects.filter(invoice__project=project)),
            0,
        )
        expenses = Expense.objects.filter(project=project, status='Approved')
        spent = sum((row.amount for row in expenses), 0)
        purchases = sum((row.amount for row in expenses.filter(category='Purchase')), 0)
        rows.append({
            'id': project.id,
            'name': project.name,
            'currency': project.currency or 'INR',
            'invoiced': invoiced,
            'collected': collected,
            'expenses': spent,
            'purchases': purchases,
            'profit': collected - spent,
            'gear': [
                {
                    'id': item.id,
                    'name': item.name,
                    'kind': item.kind,
                    'quantity': item.quantity,
                    'daily_rate': item.daily_rate,
                    'notes': item.notes,
                }
                for item in project.gear.all()
            ],
        })
    return rows


@transaction.atomic
def seed_sooryadev_bill(user=None):
    project = ensure_gaming_hub(user)
    _hub_lock()
    number = 'DPS-GH-2026-1021'
    if RentalEstimate.objects.filter(estimate_number=number).exists():
        return RentalEstimate.objects.get(estimate_number=number)
    actor = user if getattr(user, 'is_authenticated', False) else None
    if actor is None:
        from django.contrib.auth import get_user_model
        actor = get_user_model().objects.filter(is_active=True).order_by('id').first()
    if actor is None:
        return None
    return create_rental(actor, {
        'estimate_number': number,
        'customer_name': 'Sooryadev',
        'project': project.id,
        'date_issued': '2026-10-21',
        'start_date': '2026-10-11',
        'end_date': '2026-10-15',
        'delivery_location': 'Garden Court Apartments, Gandhipuram',
        'advance_amount': 500,
        'lines': [
            {'description': 'PS5 Console (DualSense included)', 'quantity': 1, 'days': 5, 'rate_per_day': 1000},
            {'description': 'Extra DualSense Controller', 'quantity': 3, 'days': 5, 'rate_per_day': 150},
            {'description': 'UPS 1250v', 'quantity': 1, 'days': 5, 'rate_per_day': 150},
        ],
    })


def _as_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])
