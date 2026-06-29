from django.db import models
from django.conf import settings

class Client(models.Model):
    CLIENT_TYPE_CHOICES = (
        ('Service Client', 'Service Client'),
        ('Product Client', 'Product Client'),
        ('Both', 'Both'),
    )

    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('On Hold', 'On Hold'),
        ('Churned', 'Churned'),
    )

    company_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    
    gstin = models.CharField(max_length=50, blank=True, null=True)
    pan = models.CharField(max_length=50, blank=True, null=True)
    logo = models.ImageField(upload_to='client_logos/', blank=True, null=True)
    
    client_type = models.CharField(max_length=50, choices=CLIENT_TYPE_CHOICES, default='Service Client')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Active')
    
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_clients'
    )
    
    support_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='supported_clients'
    )
    
    notes = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    
    onboarded_date = models.DateField(blank=True, null=True)
    contract_start = models.DateField(blank=True, null=True)
    contract_end = models.DateField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_clients'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name

    @property
    def total_revenue_generated(self):
        # Calculated from payments in future finance module integration
        return self.invoices.filter(status='Paid').aggregate(
            total=models.Sum('total_amount')
        )['total'] or 0.00


class ClientContact(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.client.company_name})"


class ClientDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ('Contract', 'Contract'),
        ('NDA', 'NDA'),
        ('Agreement', 'Agreement'),
        ('Invoice', 'Invoice'),
        ('Other', 'Other'),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES, default='Other')
    file = models.FileField(upload_to='client_documents/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.client.company_name}"
