from django.db import models
from django.conf import settings

class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = (
        ('Lead', 'Lead'),
        ('Task', 'Task'),
        ('Follow-up', 'Follow-up'),
        ('Invoice', 'Invoice'),
        ('Project', 'Project'),
        ('System', 'System'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, default='System')
    related_url = models.CharField(max_length=255, blank=True, null=True)
    
    is_read = models.BooleanField(default=False)
    
    sent_via_email = models.BooleanField(default=False)
    sent_via_whatsapp = models.BooleanField(default=False)
    sent_via_push = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} for {self.user.email} ({self.created_at})"
