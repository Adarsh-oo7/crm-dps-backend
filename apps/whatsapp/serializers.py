from datetime import datetime, timedelta, timezone

from rest_framework import serializers
from .models import WhatsAppContact, WhatsAppMessage
from .services import has_open_session


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        ts = instance.timestamp
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        stale = (
            instance.direction == "out"
            and instance.status in ("pending", "accepted")
            and ts is not None
            and datetime.now(timezone.utc) - ts > timedelta(minutes=3)
        )
        if stale:
            data["status"] = "failed"
            data["error_message"] = data.get("error_message") or "Not delivered"
        return data


class WhatsAppContactSerializer(serializers.ModelSerializer):
    session_open = serializers.SerializerMethodField()
    display_phone = serializers.SerializerMethodField()
    last_direction = serializers.SerializerMethodField()
    last_status = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppContact
        fields = (
            "id",
            "wa_id",
            "profile_name",
            "display_phone",
            "last_message_at",
            "last_message_preview",
            "unread_count",
            "session_open",
            "last_direction",
            "last_status",
        )

    def get_session_open(self, obj):
        return has_open_session(obj)

    def get_display_phone(self, obj):
        from .services import format_display_phone
        return format_display_phone(obj.wa_id)

    def _last_message(self, obj):
        last = getattr(obj, "prefetched_last", None)
        if last:
            return last[0] if isinstance(last, list) and last else last
        return obj.messages.order_by("-timestamp", "-id").first()

    def get_last_direction(self, obj):
        last = getattr(obj, "last_direction", None)
        if last:
            return last
        message = self._last_message(obj)
        return message.direction if message else ""

    def get_last_status(self, obj):
        last = getattr(obj, "last_status", None)
        if last:
            return last
        message = self._last_message(obj)
        return message.status if message else ""
