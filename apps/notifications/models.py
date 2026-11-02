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
        if not is_new:
            return

        # Check global email automation setting
        email_allowed = True
        try:
            settings_obj = SystemNotificationSetting.get_settings()
            email_allowed = settings_obj.email_automation_enabled
        except Exception:
            email_allowed = True

        prefs = getattr(self.user, 'notification_preferences', None) or {}
        if email_allowed and prefs.get('email', True) is not False and self.user.email:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                subject = f"[DPS OS] {self.title}"
                html_message = f"<p>{self.message}</p>"
                if self.related_url:
                    frontend_base = "https://crm.digitalproductsolutions.in"
                    full_url = f"{frontend_base}{self.related_url}"
                    html_message += f"<p><a href='{full_url}'>Open it in DPS</a></p>"
                send_mail(
                    subject=subject,
                    message=self.message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[self.user.email],
                    html_message=html_message,
                    fail_silently=True,
                )
                Notification.objects.filter(pk=self.pk).update(sent_via_email=True)
            except Exception:
                pass
        if prefs.get('push', True) is not False:
            try:
                from .push import send_push
                if send_push(self.user, self.title, self.message):
                    Notification.objects.filter(pk=self.pk).update(sent_via_push=True)
            except Exception:
                pass


class SystemNotificationSetting(models.Model):
    """Global system-wide notification & automation settings."""
    email_automation_enabled = models.BooleanField(
        default=True,
        help_text="Master switch: if False, automated emails (reminders, cron jobs, notifications) are paused."
    )
    email_automation_disabled_reason = models.CharField(
        max_length=255, 
        blank=True, 
        default="Turned off by Administrator"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_notification_settings'
    )

    class Meta:
        verbose_name = "System Notification Setting"
        verbose_name_plural = "System Notification Settings"

    def __str__(self):
        status = "ON" if self.email_automation_enabled else "OFF"
        return f"Email Automation: {status}"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class ReminderLog(models.Model):
    """Stops the morning and evening jobs from emailing the same person twice in one day."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reminder_logs',
    )
    kind = models.CharField(max_length=40)
    sent_on = models.DateField()

    class Meta:
        unique_together = ('user', 'kind', 'sent_on')
