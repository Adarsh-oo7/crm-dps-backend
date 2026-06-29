from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.clients.models import Client
from apps.projects.models import Project
from apps.leads.models import Lead

class Proposal(models.Model):
    STATUS_CHOICES = (
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Revised', 'Revised'),
    )
    proposal_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='proposals')
    project_name = models.CharField(max_length=255)
    description = models.TextField()
    valid_until = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    pdf_file = models.FileField(upload_to='proposals/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.proposal_number:
            year = timezone.now().year
            count = Proposal.objects.filter(created_at__year=year).count() + 1
            self.proposal_number = f"PRO-{year}-{count:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.proposal_number} - {self.client.company_name}"


class ProposalLineItem(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    order = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percent / 100)
        tax = (subtotal - discount) * (self.tax_percent / 100)
        self.total = subtotal - discount + tax
        super().save(*args, **kwargs)


class Invoice(models.Model):
    STATUS_CHOICES = (
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Partially Paid', 'Partially Paid'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled'),
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='invoices')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    invoice_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='USD')
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = timezone.now().year
            count = Invoice.objects.filter(created_at__year=year).count() + 1
            self.invoice_number = f"INV-{year}-{count:03d}"
        super().save(*args, **kwargs)

    def recalculate_totals(self):
        items = self.line_items.all()
        subtotal = sum(item.quantity * item.unit_price for item in items)
        discount = sum((item.quantity * item.unit_price) * (item.discount_percent / 100) for item in items)
        tax = sum(((item.quantity * item.unit_price) - ((item.quantity * item.unit_price) * (item.discount_percent / 100))) * (item.tax_percent / 100) for item in items)
        
        self.subtotal = subtotal
        self.discount_amount = discount
        self.tax_amount = tax
        self.total_amount = subtotal - discount + tax
        self.save()

    def __str__(self):
        return f"{self.invoice_number} - {self.client.company_name}"


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    order = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percent / 100)
        tax = (subtotal - discount) * (self.tax_percent / 100)
        self.total = subtotal - discount + tax
        super().save(*args, **kwargs)
        # Recalculate parent invoice
        self.invoice.recalculate_totals()


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=50)
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update invoice status
        total_paid = sum(p.amount for p in self.invoice.payments.all())
        if total_paid >= self.invoice.total_amount:
            self.invoice.status = 'Paid'
            self.invoice.paid_at = timezone.now()
        elif total_paid > 0:
            self.invoice.status = 'Partially Paid'
        self.invoice.save()

    def __str__(self):
        return f"PAY-{self.id:04d} for {self.invoice.invoice_number}"


class Expense(models.Model):
    CATEGORY_CHOICES = (
        ('Salary', 'Salary'),
        ('Software', 'Software'),
        ('Hosting', 'Hosting'),
        ('Marketing', 'Marketing'),
        ('Office', 'Office'),
        ('Travel', 'Travel'),
        ('Legal', 'Legal'),
        ('Equipment', 'Equipment'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    expense_date = models.DateField()
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paid_expenses')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    is_reimbursable = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount} {self.currency}"


class Quotation(models.Model):
    STATUS_CHOICES = (
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Revised', 'Revised'),
    )
    quotation_number = models.CharField(max_length=50, unique=True)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotations')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotations')
    project_description = models.TextField()
    valid_until = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    notes = models.TextField(blank=True)
    pdf_file = models.FileField(upload_to='quotations/', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            year = timezone.now().year
            count = Quotation.objects.filter(created_at__year=year).count() + 1
            self.quotation_number = f"QUO-{year}-{count:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quotation_number}"


class QuotationLineItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    order = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percent / 100)
        tax = (subtotal - discount) * (self.tax_percent / 100)
        self.total = subtotal - discount + tax
        super().save(*args, **kwargs)
