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

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                subject = f"[DPS OS] {self.title}"
                html_message = f"<p>{self.message}</p>"
                if self.related_url:
                    frontend_base = "https://crm.digitalproductsolutions.in"
                    full_url = f"{frontend_base}{self.related_url}"
                    html_message += f"<p><a href='{full_url}'>Click here to view</a></p>"
                send_mail(
                    subject=subject,
                    message=self.message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[self.user.email],
                    html_message=html_message,
                    fail_silently=True
                )
                Notification.objects.filter(pk=self.pk).update(sent_via_email=True)
            except Exception:
                pass
