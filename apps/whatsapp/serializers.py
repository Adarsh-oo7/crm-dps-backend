from rest_framework import serializers
from .models import WhatsAppContact, WhatsAppMessage


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    sent_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppMessage
        fields = (
            "id",
            "wamid",
            "direction",
            "message_type",
            "text",
            "status",
            "error_message",
            "timestamp",
            "sent_by",
            "sent_by_name",
        )

    def get_sent_by_name(self, obj):
        return obj.sent_by.full_name if obj.sent_by else ""


class WhatsAppContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppContact
        fields = (
            "id",
            "wa_id",
            "profile_name",
            "last_message_at",
            "last_message_preview",
            "unread_count",
        )
