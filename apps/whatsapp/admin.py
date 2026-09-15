from django.contrib import admin
from .models import WhatsAppContact, WhatsAppMessage


@admin.register(WhatsAppContact)
class WhatsAppContactAdmin(admin.ModelAdmin):
    list_display = ("wa_id", "profile_name", "unread_count", "last_message_at")
    search_fields = ("wa_id", "profile_name")


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("contact", "direction", "status", "message_type", "timestamp")
    list_filter = ("direction", "status", "message_type")
    search_fields = ("text", "wamid", "contact__wa_id")
