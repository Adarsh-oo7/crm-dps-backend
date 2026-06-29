from django.db import models
from django.conf import settings

class Product(models.Model):
    TYPE_CHOICES = (
        ('SaaS', 'SaaS'),
        ('Mobile App', 'Mobile App'),
        ('Web App', 'Web App'),
        ('API', 'API'),
    )
    STATUS_CHOICES = (
        ('Idea', 'Idea'),
        ('Planning', 'Planning'),
        ('Development', 'Development'),
        ('Beta', 'Beta'),
        ('Live', 'Live'),
        ('Paused', 'Paused'),
        ('Discontinued', 'Discontinued'),
    )
    PRICING_CHOICES = (
        ('Free', 'Free'),
        ('Freemium', 'Freemium'),
        ('Paid', 'Paid'),
        ('Subscription', 'Subscription'),
    )
    name = models.CharField(max_length=255)
    description = models.TextField()
    product_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Idea')
    tagline = models.CharField(max_length=255, blank=True)
    website_url = models.URLField(blank=True)
    app_store_url = models.URLField(blank=True)
    play_store_url = models.URLField(blank=True)
    github_repo = models.URLField(blank=True)
    tech_stack = models.JSONField(default=list, blank=True)
    pricing_model = models.CharField(max_length=50, choices=PRICING_CHOICES, default='Free')
    monthly_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    project_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_products')
    team_members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='products_working_on')
    launch_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductFeature(models.Model):
    STATUS_CHOICES = (
        ('Backlog', 'Backlog'),
        ('Planned', 'Planned'),
        ('In Development', 'In Development'),
        ('Done', 'Done'),
        ('Cancelled', 'Cancelled'),
    )
    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='features')
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Backlog')
    priority = models.CharField(max_length=50, choices=PRIORITY_CHOICES, default='Medium')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_features')
    target_version = models.CharField(max_length=50, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.product.name}"


class ProductBug(models.Model):
    SEVERITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    )
    STATUS_CHOICES = (
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Fixed', 'Fixed'),
        ('Closed', 'Closed'),
        ('Wont Fix', 'Wont Fix'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bugs')
    title = models.CharField(max_length=255)
    description = models.TextField()
    steps_to_reproduce = models.TextField(blank=True)
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES, default='Medium')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Open')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reported_bugs')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bugs')
    environment = models.CharField(max_length=50, default='Production')
    browser_os = models.CharField(max_length=255, blank=True)
    screenshot = models.ImageField(upload_to='product_bugs/', null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.product.name} ({self.severity})"
