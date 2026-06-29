from django.db import models
from django.conf import settings

class FollowUp(models.Model):
    FOLLOW_UP_TYPE_CHOICES = (
        ('Call', 'Call'),
        ('Email', 'Email'),
        ('Meeting', 'Meeting'),
        ('WhatsApp', 'WhatsApp'),
        ('Proposal', 'Proposal'),
        ('Demo', 'Demo'),
        ('Quotation', 'Quotation'),
        ('Check-in', 'Check-in'),
        ('Other', 'Other'),
    )

    RELATED_TO_TYPE_CHOICES = (
        ('Lead', 'Lead'),
        ('Client', 'Client'),
        ('Project', 'Project'),
        ('General', 'General'),
    )

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Missed', 'Missed'),
        ('Rescheduled', 'Rescheduled'),
        ('Cancelled', 'Cancelled'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    follow_up_type = models.CharField(max_length=50, choices=FOLLOW_UP_TYPE_CHOICES, default='Call')
    related_to_type = models.CharField(max_length=50, choices=RELATED_TO_TYPE_CHOICES, default='General')
    related_to_id = models.IntegerField(blank=True, null=True) # ID of lead/client/project
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_followups'
    )
    
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    
    reminder_sent = models.BooleanField(default=False)
    reminder_at = models.DateTimeField(blank=True, null=True)
    
    outcome = models.TextField(blank=True, null=True)
    reschedule_count = models.IntegerField(default=0)
    
    next_follow_up = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='previous_followups'
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_followups'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.status} ({self.scheduled_at})"
