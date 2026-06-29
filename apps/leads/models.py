from django.db import models
from django.conf import settings

class Lead(models.Model):
    LEAD_SOURCE_CHOICES = (
        ('Website', 'Website'),
        ('LinkedIn', 'LinkedIn'),
        ('Referral', 'Referral'),
        ('Cold Email', 'Cold Email'),
        ('WhatsApp', 'WhatsApp'),
        ('Event', 'Event'),
        ('Other', 'Other'),
    )

    STATUS_CHOICES = (
        ('New', 'New'),
        ('Contacted', 'Contacted'),
        ('Meeting Scheduled', 'Meeting Scheduled'),
        ('Proposal Sent', 'Proposal Sent'),
        ('Negotiation', 'Negotiation'),
        ('Won', 'Won'),
        ('Lost', 'Lost'),
        ('On Hold', 'On Hold'),
    )

    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Hot', 'Hot'),
    )

    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    
    lead_source = models.CharField(max_length=50, choices=LEAD_SOURCE_CHOICES, default='Other')
    lead_score = models.IntegerField(default=50) # 1-100
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='New')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='USD')
    
    notes = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    
    next_followup_date = models.DateTimeField(blank=True, null=True)
    next_followup_note = models.TextField(blank=True, null=True)
    lost_reason = models.TextField(blank=True, null=True)
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_leads'
    )
    project = models.ForeignKey(
        'projects.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='leads'
    )
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='leads'
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_leads'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} ({self.contact_person})"


class LeadActivityTimeline(models.Model):
    ACTIVITY_TYPE_CHOICES = (
        ('Call', 'Call'),
        ('Email', 'Email'),
        ('Meeting', 'Meeting'),
        ('Note', 'Note'),
        ('Status Change', 'Status Change'),
        ('Follow-up', 'Follow-up'),
        ('WhatsApp', 'WhatsApp'),
        ('Proposal Sent', 'Proposal Sent'),
    )

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.activity_type} - {self.lead.company_name} ({self.created_at})"
