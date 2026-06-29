from django.db import models
from django.conf import settings
from apps.clients.models import Client
from apps.projects.models import Project

class Domain(models.Model):
    REGISTRAR_CHOICES = (
        ('GoDaddy', 'GoDaddy'),
        ('Namecheap', 'Namecheap'),
        ('Google Domains', 'Google Domains'),
        ('Dynadot', 'Dynadot'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Expired', 'Expired'),
        ('Transferred', 'Transferred'),
    )
    domain_name = models.CharField(max_length=255, unique=True)
    registrar = models.CharField(max_length=50, choices=REGISTRAR_CHOICES, default='Namecheap')
    registered_date = models.DateField()
    expiry_date = models.DateField()
    auto_renew = models.BooleanField(default=False)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='domains')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='domains')
    nameservers = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    login_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.domain_name


class Hosting(models.Model):
    SERVER_TYPE_CHOICES = (
        ('VPS', 'VPS'),
        ('Shared', 'Shared'),
        ('Dedicated', 'Dedicated'),
        ('Cloud', 'Cloud'),
    )
    PROVIDER_CHOICES = (
        ('DigitalOcean', 'DigitalOcean'),
        ('Vultr', 'Vultr'),
        ('AWS', 'AWS'),
        ('GCP', 'GCP'),
        ('Linode', 'Linode'),
        ('Hostinger', 'Hostinger'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Suspended', 'Suspended'),
        ('Expired', 'Expired'),
    )
    server_name = models.CharField(max_length=255)
    server_type = models.CharField(max_length=20, choices=SERVER_TYPE_CHOICES, default='VPS')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='DigitalOcean')
    ip_address = models.GenericIPAddressField()
    location = models.CharField(max_length=100, blank=True)
    plan_name = models.CharField(max_length=100, blank=True)
    monthly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='USD')
    start_date = models.DateField()
    renewal_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    username = models.CharField(max_length=100, blank=True)
    root_access = models.BooleanField(default=False)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='hostings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    ram_gb = models.IntegerField(default=1)
    storage_gb = models.IntegerField(default=20)
    bandwidth_gb = models.IntegerField(default=1000)
    cpu_cores = models.IntegerField(default=1)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.server_name} ({self.ip_address})"


class SSLCertificate(models.Model):
    ISSUER_CHOICES = (
        ("Let's Encrypt", "Let's Encrypt"),
        ('Comodo', 'Comodo'),
        ('DigiCert', 'DigiCert'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Valid', 'Valid'),
        ('Expired', 'Expired'),
        ('Expiring Soon', 'Expiring Soon'),
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='ssl_certificates')
    issuer = models.CharField(max_length=50, choices=ISSUER_CHOICES, default="Let's Encrypt")
    issued_date = models.DateField()
    expiry_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Valid')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SSL for {self.domain.domain_name}"
