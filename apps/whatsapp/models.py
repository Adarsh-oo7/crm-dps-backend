from django.conf import settings
from django.db import models


class WhatsAppAccount(models.Model):
    waba_id = models.CharField(max_length=32, blank=True)
    phone_number_id = models.CharField(max_length=32)
    display_phone_number = models.CharField(max_length=32, blank=True)
    verified_name = models.CharField(max_length=255, blank=True)
    business_id = models.CharField(max_length=32, blank=True)
    access_token = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_accounts",
    )
    raw_session = models.JSONField(default=dict, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-connected_at"]

    def __str__(self):
        return self.display_phone_number or self.phone_number_id


class WhatsAppContact(models.Model):
    wa_id = models.CharField(max_length=32, unique=True, db_index=True)
    profile_name = models.CharField(max_length=255, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=500, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-updated_at"]

    def __str__(self):
        return self.profile_name or self.wa_id


class WhatsAppMessage(models.Model):
    DIRECTION_CHOICES = (
        ("in", "Incoming"),
        ("out", "Outgoing"),
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
    )

    contact = models.ForeignKey(
        WhatsAppContact, on_delete=models.CASCADE, related_name="messages"
    )
    wamid = models.CharField(max_length=255, unique=True, null=True, blank=True)
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=40, default="text")
    text = models.TextField(blank=True)
    media_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField()
    raw_payload = models.JSONField(default=dict, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp", "id"]
        indexes = [
            models.Index(fields=["contact", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.direction} {self.contact.wa_id}: {self.text[:40]}"
