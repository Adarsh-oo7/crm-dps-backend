import logging
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

from .models import WhatsAppContact, WhatsAppMessage

log = logging.getLogger(__name__)


def normalize_wa_id(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("0") and len(digits) == 11:
        digits = "91" + digits[1:]
    return digits


def graph_url(path: str) -> str:
    version = getattr(settings, "WHATSAPP_GRAPH_VERSION", "v21.0")
    return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"


def is_configured() -> bool:
    return bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def _preview(text: str, message_type: str) -> str:
    body = (text or "").strip()
    if body:
        return body[:180]
    return {
        "image": "Photo",
        "audio": "Voice message",
        "video": "Video",
        "document": "Document",
        "sticker": "Sticker",
        "location": "Location",
        "contacts": "Contact",
        "interactive": "Interactive message",
        "button": "Button reply",
        "template": "Template message",
    }.get(message_type, "Message")


def _timestamp(value) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    parsed = parse_datetime(str(value))
    if parsed:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)


def get_or_create_contact(wa_id: str, profile_name: str = "") -> WhatsAppContact:
    wa_id = normalize_wa_id(wa_id)
    contact, _ = WhatsAppContact.objects.get_or_create(wa_id=wa_id)
    if profile_name and contact.profile_name != profile_name:
        contact.profile_name = profile_name
        contact.save(update_fields=["profile_name", "updated_at"])
    return contact


def extract_message_text(msg: dict) -> tuple[str, str, str]:
    message_type = msg.get("type") or "unknown"
    media_id = ""
    if message_type == "text":
        return msg.get("text", {}).get("body", ""), message_type, media_id
    if message_type == "button":
        return msg.get("button", {}).get("text", ""), message_type, media_id
    if message_type == "interactive":
        interactive = msg.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title") or reply.get("id") or "Interactive reply", message_type, media_id
    if message_type in ("image", "video", "audio", "document", "sticker"):
        payload = msg.get(message_type) or {}
        media_id = payload.get("id", "")
        caption = payload.get("caption") or payload.get("filename") or ""
        return caption, message_type, media_id
    if message_type == "location":
        loc = msg.get("location") or {}
        return loc.get("name") or f"{loc.get('latitude')}, {loc.get('longitude')}", message_type, media_id
    return "", message_type, media_id


def ingest_webhook(payload: dict) -> None:
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            contacts = {c.get("wa_id"): c for c in (value.get("contacts") or []) if c.get("wa_id")}

            for msg in value.get("messages") or []:
                wa_id = normalize_wa_id(msg.get("from", ""))
                if not wa_id:
                    continue
                profile_name = (contacts.get(msg.get("from")) or {}).get("profile", {}).get("name", "")
                contact = get_or_create_contact(wa_id, profile_name)
                text, message_type, media_id = extract_message_text(msg)
                wamid = msg.get("id")
                if wamid and WhatsAppMessage.objects.filter(wamid=wamid).exists():
                    continue
                ts = _timestamp(msg.get("timestamp"))
                WhatsAppMessage.objects.create(
                    contact=contact,
                    wamid=wamid,
                    direction="in",
                    message_type=message_type,
                    text=text,
                    media_id=media_id,
                    status="delivered",
                    timestamp=ts,
                    raw_payload=msg,
                )
                contact.last_message_at = ts
                contact.last_message_preview = _preview(text, message_type)
                contact.unread_count = (contact.unread_count or 0) + 1
                contact.save(update_fields=["last_message_at", "last_message_preview", "unread_count", "updated_at"])

            for status_event in value.get("statuses") or []:
                wamid = status_event.get("id")
                if not wamid:
                    continue
                message = WhatsAppMessage.objects.filter(wamid=wamid).first()
                if not message:
                    continue
                new_status = status_event.get("status") or message.status
                if new_status in dict(WhatsAppMessage.STATUS_CHOICES):
                    message.status = new_status
                errors = status_event.get("errors") or []
                if errors:
                    message.error_message = errors[0].get("title") or errors[0].get("message") or str(errors[0])
                    message.status = "failed"
                message.save(update_fields=["status", "error_message"])


def send_text_message(to: str, text: str, sent_by=None) -> WhatsAppMessage:
    if not is_configured():
        raise RuntimeError("WhatsApp Cloud API is not configured. Add WHATSAPP_ACCESS_TOKEN on the server.")

    wa_id = normalize_wa_id(to)
    if not wa_id:
        raise ValueError("Enter a valid WhatsApp number.")
    body = (text or "").strip()
    if not body:
        raise ValueError("Message cannot be empty.")

    contact = get_or_create_contact(wa_id)
    now = datetime.now(timezone.utc)
    message = WhatsAppMessage.objects.create(
        contact=contact,
        direction="out",
        message_type="text",
        text=body,
        status="pending",
        timestamp=now,
        sent_by=sent_by if getattr(sent_by, "is_authenticated", False) else None,
    )

    response = requests.post(
        graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"),
        headers={
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        },
        timeout=20,
    )

    data = {}
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}

    message.raw_payload = data
    if not response.ok:
        error = (data.get("error") or {})
        message.status = "failed"
        message.error_message = error.get("message") or response.text[:500]
        message.save(update_fields=["status", "error_message", "raw_payload"])
        raise RuntimeError(message.error_message)

    wamid = ((data.get("messages") or [{}])[0]).get("id")
    message.wamid = wamid
    message.status = ((data.get("messages") or [{}])[0]).get("message_status") or "accepted"
    if message.status not in dict(WhatsAppMessage.STATUS_CHOICES):
        message.status = "accepted"
    message.save(update_fields=["wamid", "status", "raw_payload"])

    contact.last_message_at = now
    contact.last_message_preview = _preview(body, "text")
    contact.save(update_fields=["last_message_at", "last_message_preview", "updated_at"])
    return message


def mark_contact_read(contact: WhatsAppContact) -> None:
    last_inbound = (
        contact.messages.filter(direction="in", wamid__isnull=False).order_by("-timestamp").first()
    )
    contact.unread_count = 0
    contact.save(update_fields=["unread_count", "updated_at"])
    if not last_inbound or not is_configured():
        return
    try:
        requests.post(
            graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"),
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": last_inbound.wamid,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        log.warning("Could not mark WhatsApp message as read: %s", exc)
