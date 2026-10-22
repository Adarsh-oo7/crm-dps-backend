import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import mimetypes
from pathlib import Path

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from .models import (
    WhatsAppAccount,
    WhatsAppBusiness,
    WhatsAppContact,
    WhatsAppMessage,
    WhatsAppPhoneNumber,
    WhatsAppSyncLog,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
)
from .access import account_for_webhook
from .meta_client import MetaWhatsAppClient

log = logging.getLogger(__name__)

LAST_WEBHOOK_CACHE = "whatsapp:last_webhook_at"
SESSION_HOURS = 24
CUSTOM_TEMPLATE = "dps_chat_message"
CUSTOM_TEMPLATE_LANG = "en"
HELLO_TEMPLATE = "hello_world"
HELLO_TEMPLATE_LANG = "en_US"
BILLING_URL = (
    "https://business.facebook.com/billing_hub/accounts/details/"
    "?business_id=622580630220380&asset_id=1619899406510846"
    "&wizard_name=ADD_PM&account_type=whatsapp-business-account"
)


def normalize_wa_id(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = "91" + digits[1:]
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def format_display_phone(value: str) -> str:
    digits = normalize_wa_id(value)
    if len(digits) == 12 and digits.startswith("91"):
        return f"+91 {digits[2:7]} {digits[7:]}"
    if digits:
        return f"+{digits}"
    return ""


SKIP_INBOUND_TYPES = {
    "system",
    "request_welcome",
    "unsupported",
    "reaction",
    "ephemeral",
    "unknown",
}


def get_or_create_contact(wa_id: str, profile_name: str = "", account: Optional[WhatsAppAccount] = None) -> WhatsAppContact:
    wa_id = normalize_wa_id(wa_id)
    qs = WhatsAppContact.objects.all()
    if account:
        qs = qs.filter(account=account)
    contact = qs.filter(wa_id=wa_id).first()
    if not contact and len(wa_id) >= 10:
        tail = wa_id[-10:]
        aliases = list(qs.filter(wa_id__endswith=tail))
        if aliases:
            contact = next((row for row in aliases if row.wa_id == wa_id), aliases[0])
            if contact.wa_id != wa_id:
                existing = qs.filter(wa_id=wa_id).first()
                if existing:
                    contact = existing
                else:
                    contact.wa_id = wa_id
                    contact.save(update_fields=["wa_id", "updated_at"])
            for extra in aliases:
                if extra.id == contact.id:
                    continue
                extra.messages.update(contact=contact)
                extra.delete()
    if not contact:
        contact = WhatsAppContact.objects.create(wa_id=wa_id, account=account)
    elif account and contact.account_id is None:
        contact.account = account
        contact.save(update_fields=["account", "updated_at"])
    if len(wa_id) >= 10:
        tail = wa_id[-10:]
        extras = WhatsAppContact.objects.filter(wa_id__endswith=tail).exclude(pk=contact.pk)
        if account:
            extras = extras.filter(account=account)
        for extra in extras:
            extra.messages.update(contact=contact)
            extra.delete()
    if profile_name and contact.profile_name != profile_name:
        contact.profile_name = profile_name
        contact.save(update_fields=["profile_name", "updated_at"])
    link_crm_records(contact)
    return contact


def link_crm_records(contact: WhatsAppContact) -> None:
    if contact.lead_id and contact.client_id:
        return
    tail = contact.wa_id[-10:] if len(contact.wa_id) >= 10 else contact.wa_id
    if not tail:
        return
    updates = []
    if not contact.lead_id:
        from apps.leads.models import Lead
        lead = Lead.objects.filter(phone__icontains=tail).first()
        if lead:
            contact.lead = lead
            updates.extend(["lead", "updated_at"])
    if not contact.client_id:
        from apps.clients.models import ClientContact
        row = ClientContact.objects.filter(Q_whatsapp_or_phone(tail)).select_related("client").first()
        if row:
            contact.client_contact = row
            contact.client = row.client
            updates.extend(["client_contact", "client", "updated_at"])
    if updates:
        contact.save(update_fields=list(dict.fromkeys(updates)))


def Q_whatsapp_or_phone(tail: str):
    from django.db.models import Q
    return Q(whatsapp__icontains=tail) | Q(phone__icontains=tail)


def graph_url(path: str) -> str:
    version = getattr(settings, "WHATSAPP_GRAPH_VERSION", "v21.0")
    return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"


def active_account() -> Optional[WhatsAppAccount]:
    return WhatsAppAccount.objects.filter(is_active=True).order_by("-connected_at").first()


def graph_token() -> str:
    account = active_account()
    return (account.access_token if account and account.access_token else settings.WHATSAPP_ACCESS_TOKEN) or ""


def graph_headers() -> dict:
    return {
        "Authorization": f"Bearer {graph_token()}",
        "Content-Type": "application/json",
    }


def is_configured() -> bool:
    account = active_account()
    if account and account.phone_number_id:
        return True
    return bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def waba_id() -> str:
    account = active_account()
    if account and account.waba_id:
        return account.waba_id
    return getattr(settings, "WHATSAPP_WABA_ID", "") or "1619899406510846"


def phone_number_id() -> str:
    account = active_account()
    if account and account.phone_number_id:
        return account.phone_number_id
    return settings.WHATSAPP_PHONE_NUMBER_ID


def display_number() -> str:
    account = active_account()
    if account and account.display_phone_number:
        return account.display_phone_number
    return settings.WHATSAPP_DISPLAY_NUMBER


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


def has_open_session(contact: WhatsAppContact) -> bool:
    last_in = contact.messages.filter(direction="in").order_by("-timestamp").first()
    if not last_in or not last_in.timestamp:
        return False
    ts = last_in.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ts <= timedelta(hours=SESSION_HOURS)


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
    if message_type == "template":
        return "Template message", message_type, media_id
    return "", message_type, media_id


def mark_webhook_seen() -> None:
    cache.set(LAST_WEBHOOK_CACHE, datetime.now(timezone.utc).isoformat(), None)


def last_webhook_at() -> str:
    return cache.get(LAST_WEBHOOK_CACHE) or ""


PROFILE_CACHE = "whatsapp:business_profile"


def business_profile() -> dict:
    cached = cache.get(PROFILE_CACHE)
    if isinstance(cached, dict):
        return cached
    data = {"profile_picture_url": "", "about": "", "verified_name": ""}
    if not is_configured():
        return data
    try:
        response = requests.get(
            graph_url(f"{phone_number_id()}/whatsapp_business_profile"),
            headers=graph_headers(),
            params={"fields": "profile_picture_url,about,description,email,websites,vertical,address"},
            timeout=15,
        )
        payload = response.json() if response.content else {}
        rows = payload.get("data") if isinstance(payload, dict) else None
        row = rows[0] if isinstance(rows, list) and rows else (payload if isinstance(payload, dict) else {})
        data["profile_picture_url"] = row.get("profile_picture_url") or ""
        data["about"] = row.get("about") or row.get("description") or ""
    except requests.RequestException as exc:
        log.warning("Could not load WhatsApp business profile: %s", exc)
    try:
        response = requests.get(
            graph_url(phone_number_id()),
            headers=graph_headers(),
            params={"fields": "verified_name,display_phone_number,quality_rating"},
            timeout=15,
        )
        payload = response.json() if response.content else {}
        data["verified_name"] = payload.get("verified_name") or ""
        if payload.get("display_phone_number"):
            data["display_phone_number"] = payload.get("display_phone_number")
    except requests.RequestException:
        pass
    cache.set(PROFILE_CACHE, data, 3600)
    return data


def merge_duplicate_contacts() -> None:
    grouped: dict[tuple, list[WhatsAppContact]] = {}
    for contact in WhatsAppContact.objects.all():
        tail = contact.wa_id[-10:] if len(contact.wa_id) >= 10 else contact.wa_id
        grouped.setdefault((contact.account_id, tail), []).append(contact)
    for rows in grouped.values():
        if not rows:
            continue
        preferred = max(rows, key=lambda row: (len(row.wa_id), row.messages.count(), row.id))
        canonical_id = normalize_wa_id(preferred.wa_id)
        if preferred.wa_id != canonical_id:
            clash = WhatsAppContact.objects.filter(account_id=preferred.account_id, wa_id=canonical_id).exclude(pk=preferred.pk).first()
            if clash:
                preferred = clash
            else:
                preferred.wa_id = canonical_id
                preferred.save(update_fields=["wa_id", "updated_at"])
        for extra in rows:
            if extra.pk == preferred.pk:
                continue
            extra.messages.update(contact=preferred)
            if extra.profile_name and not preferred.profile_name:
                preferred.profile_name = extra.profile_name
                preferred.save(update_fields=["profile_name", "updated_at"])
            extra.delete()


def prune_noise_contacts() -> None:
    own = normalize_wa_id(display_number())
    if own:
        WhatsAppContact.objects.filter(wa_id=own).delete()
    for contact in WhatsAppContact.objects.all():
        if not contact.messages.exclude(text="").exists():
            contact.delete()


def ingest_webhook(payload: dict) -> None:
    mark_webhook_seen()
    if not isinstance(payload, dict):
        return
    log.info("WhatsApp webhook: %s", str(payload)[:4000])

    for entry in payload.get("entry") or []:
        waba_id_value = str(entry.get("id") or "")
        for change in (entry.get("changes") or []):
            field = change.get("field") or "messages"
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_id = str(metadata.get("phone_number_id") or "")
            account = account_for_webhook(phone_id, waba_id_value)
            if account:
                account.last_webhook_at = datetime.now(timezone.utc)
                account.save(update_fields=["last_webhook_at", "updated_at"])
            if field in ("smb_app_state_sync", "state_sync"):
                _ingest_state_sync(account, value)
                continue
            if field == "history":
                _ingest_history(account, value)
                continue
            source = WhatsAppMessage.SOURCE_BIZ_APP if field in ("smb_message_echoes", "message_echoes") else WhatsAppMessage.SOURCE_CUSTOMER
            _ingest_messages(account, value, source=source, phone_id=phone_id)
            _ingest_statuses(value)


def _profile_name_from_contacts(contacts: dict, wa_id: str, raw_from: str) -> str:
    for cid, meta in contacts.items():
        if normalize_wa_id(cid) == wa_id or cid == raw_from:
            return (meta.get("profile") or {}).get("name", "")
    return ""


def _ingest_messages(account, value, source: str, phone_id: str = "") -> None:
    contacts = {c.get("wa_id"): c for c in (value.get("contacts") or []) if c.get("wa_id")}
    own = normalize_wa_id((account.display_phone_number if account else "") or display_number())
    rows = list(value.get("messages") or []) + list(value.get("message_echoes") or [])
    for msg in rows:
        raw_from = msg.get("from", "")
        raw_to = msg.get("to", "")
        wa_id = normalize_wa_id(raw_from)
        direction = "in"
        message_source = source
        if source == WhatsAppMessage.SOURCE_BIZ_APP:
            direction = "out"
            message_source = WhatsAppMessage.SOURCE_BIZ_APP
            counterpart = normalize_wa_id(raw_to) or normalize_wa_id((msg.get("recipient_id") or ""))
            if counterpart:
                wa_id = counterpart
            elif own and wa_id == own:
                continue
        if own and wa_id == own and direction == "in":
            continue
        if not wa_id:
            continue
        text, message_type, media_id = extract_message_text(msg)
        if message_type in SKIP_INBOUND_TYPES and not text:
            continue
        if not text and message_type not in ("image", "video", "audio", "document", "sticker", "location", "contacts", "text", "button", "interactive"):
            continue
        profile_name = _profile_name_from_contacts(contacts, wa_id, raw_from)
        contact = get_or_create_contact(wa_id, profile_name, account=account)
        wamid = msg.get("id")
        if wamid and WhatsAppMessage.objects.filter(wamid=wamid).exists():
            continue
        ts = _timestamp(msg.get("timestamp"))
        if direction == "in":
            message_source = WhatsAppMessage.SOURCE_CUSTOMER
        WhatsAppMessage.objects.create(
            account=account,
            contact=contact,
            wamid=wamid,
            direction=direction,
            message_type=message_type,
            text=text,
            media_id=media_id,
            status="delivered" if direction == "in" else "sent",
            source=message_source,
            phone_number_id=phone_id or (account.phone_number_id if account else ""),
            timestamp=ts,
            raw_payload=msg,
        )
        contact.last_message_at = ts
        contact.last_message_preview = _preview(text, message_type)
        if direction == "in":
            contact.unread_count = (contact.unread_count or 0) + 1
        contact.save(update_fields=["last_message_at", "last_message_preview", "unread_count", "updated_at"])


def _ingest_statuses(value: dict) -> None:
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
            err = errors[0] if isinstance(errors[0], dict) else {}
            message.error_message = err.get("title") or err.get("message") or str(errors[0])
            message.status = "failed"
        message.save(update_fields=["status", "error_message"])


def _ingest_history(account, value: dict) -> None:
    for chunk in value.get("history") or value.get("threads") or []:
        threads = chunk.get("threads") if isinstance(chunk, dict) else None
        if threads is None and isinstance(chunk, dict) and chunk.get("messages"):
            threads = [chunk]
        for thread in threads or []:
            fake_value = {
                "contacts": thread.get("contacts") or value.get("contacts") or [],
                "messages": thread.get("messages") or [],
            }
            _ingest_messages(account, fake_value, source=WhatsAppMessage.SOURCE_CUSTOMER, phone_id=account.phone_number_id if account else "")
    if account:
        WhatsAppSyncLog.objects.create(account=account, kind="history", status="ok", finished_at=datetime.now(timezone.utc))
        account.last_sync_at = datetime.now(timezone.utc)
        account.sync_status = WhatsAppAccount.SYNC_CONNECTED
        account.save(update_fields=["last_sync_at", "sync_status", "updated_at"])


def _ingest_state_sync(account, value: dict) -> None:
    for item in value.get("state_sync") or value.get("contacts") or []:
        wa_id = normalize_wa_id(item.get("phone_number") or item.get("wa_id") or item.get("id") or "")
        if not wa_id:
            continue
        name = (item.get("full_name") or item.get("name") or (item.get("profile") or {}).get("name") or "")
        get_or_create_contact(wa_id, name, account=account)
    if account:
        WhatsAppSyncLog.objects.create(account=account, kind="smb_app_state_sync", status="ok", finished_at=datetime.now(timezone.utc))
        account.is_on_biz_app = True
        if account.platform_type == WhatsAppAccount.PLATFORM_CLOUD:
            account.platform_type = WhatsAppAccount.PLATFORM_COEXISTENCE
        account.save(update_fields=["is_on_biz_app", "platform_type", "updated_at"])


def verify_webhook_signature(raw_body: bytes, header_sig: str) -> bool:
    secret = meta_app_secret()
    if not secret:
        log.warning("META_APP_SECRET is empty; webhook signature is not verified")
        return True
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig or "")


def record_webhook_event(payload: dict, raw_body: bytes) -> WhatsAppWebhookEvent:
    digest = hashlib.sha256(raw_body or json_bytes(payload)).hexdigest()
    event, created = WhatsAppWebhookEvent.objects.get_or_create(
        event_hash=digest,
        defaults={"payload": payload or {}},
    )
    if payload:
        first = (payload.get("entry") or [{}])[0]
        change = ((first.get("changes") or [{}])[0])
        value = change.get("value") or {}
        event.waba_id = str(first.get("id") or "")
        event.phone_number_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
        event.field = change.get("field") or ""
        if not event.payload:
            event.payload = payload
        event.save(update_fields=["waba_id", "phone_number_id", "field", "payload"])
    return event


def json_bytes(payload: dict) -> bytes:
    import json
    return json.dumps(payload or {}, sort_keys=True, default=str).encode("utf-8")


def process_webhook_payload(payload: dict, raw_body: bytes = b"") -> None:
    event = record_webhook_event(payload, raw_body)
    if event.processed_at:
        return
    try:
        ingest_webhook(payload)
        event.processed_at = datetime.now(timezone.utc)
        event.error = ""
        event.save(update_fields=["processed_at", "error"])
    except Exception as exc:
        event.error = str(exc)[:2000]
        event.save(update_fields=["error"])
        raise


def list_templates() -> list[dict]:
    if not is_configured():
        return []
    try:
        response = requests.get(
            graph_url(f"{waba_id()}/message_templates"),
            headers=graph_headers(),
            params={"fields": "name,status,language,category", "limit": 50},
            timeout=20,
        )
        data = response.json() if response.content else {}
    except requests.RequestException as exc:
        log.warning("Could not list WhatsApp templates: %s", exc)
        return []
    rows = []
    for item in data.get("data") or []:
        rows.append({
            "name": item.get("name"),
            "status": item.get("status"),
            "language": item.get("language"),
            "category": item.get("category"),
        })
    return rows


def pick_start_template() -> tuple[str, str, bool]:
    """Returns (name, language, uses_body_param)."""
    approved = [item for item in list_templates() if item.get("status") == "APPROVED"]
    for item in approved:
        if item.get("name") == CUSTOM_TEMPLATE:
            return CUSTOM_TEMPLATE, item.get("language") or CUSTOM_TEMPLATE_LANG, True
    for item in approved:
        if item.get("name") == HELLO_TEMPLATE:
            return HELLO_TEMPLATE, item.get("language") or HELLO_TEMPLATE_LANG, False
    if approved:
        first = approved[0]
        return first.get("name") or HELLO_TEMPLATE, first.get("language") or "en", False
    return HELLO_TEMPLATE, HELLO_TEMPLATE_LANG, False


def friendly_send_error(exc: Exception) -> RuntimeError:
    text = str(exc)
    lowered = text.lower()
    if any(token in lowered for token in ("131042", "payment", "eligibility", "billing")):
        return RuntimeError(
            "First messages must use a WhatsApp template, and Meta requires a payment method on the WhatsApp Business account. "
            f"Add one here, then send again: {BILLING_URL} "
            "After the customer replies, normal chat is free for 24 hours."
        )
    return exc if isinstance(exc, RuntimeError) else RuntimeError(text)


def _store_outgoing(contact, text, message_type, sent_by) -> WhatsAppMessage:
    now = datetime.now(timezone.utc)
    return WhatsAppMessage.objects.create(
        contact=contact,
        account=getattr(contact, "account", None),
        phone_number_id=(contact.account.phone_number_id if getattr(contact, "account", None) else phone_number_id()),
        source=WhatsAppMessage.SOURCE_CLOUD,
        direction="out",
        message_type=message_type,
        text=text,
        status="pending",
        timestamp=now,
        sent_by=sent_by if getattr(sent_by, "is_authenticated", False) else None,
    )


def _apply_graph_response(message: WhatsAppMessage, contact: WhatsAppContact, response) -> WhatsAppMessage:
    data = {}
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}

    message.raw_payload = data
    if not response.ok:
        message.status = "failed"
        message.error_message = _graph_error_message(data, response.text[:500] if response.text else "WhatsApp rejected the message.")
        message.save(update_fields=["status", "error_message", "raw_payload"])
        raise RuntimeError(message.error_message)

    wamid = ((data.get("messages") or [{}])[0]).get("id")
    message.wamid = wamid
    message.status = ((data.get("messages") or [{}])[0]).get("message_status") or "accepted"
    if message.status not in dict(WhatsAppMessage.STATUS_CHOICES):
        message.status = "accepted"
    message.save(update_fields=["wamid", "status", "raw_payload"])

    contact.last_message_at = message.timestamp
    contact.last_message_preview = _preview(message.text, message.message_type)
    contact.save(update_fields=["last_message_at", "last_message_preview", "updated_at"])
    return message


def _post_messages(payload: dict):
    try:
        return requests.post(
            graph_url(f"{phone_number_id()}/messages"),
            headers=graph_headers(),
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(str(exc)) from exc


def send_session_text(contact: WhatsAppContact, body: str, sent_by=None) -> WhatsAppMessage:
    message = _store_outgoing(contact, body, "text", sent_by)
    try:
        response = _post_messages({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": contact.wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        })
    except RuntimeError as exc:
        message.status = "failed"
        message.error_message = str(exc)
        message.save(update_fields=["status", "error_message"])
        raise
    return _apply_graph_response(message, contact, response)


IMAGE_LIMIT = 5 * 1024 * 1024
AUDIO_LIMIT = 16 * 1024 * 1024
VIDEO_LIMIT = 16 * 1024 * 1024
DOCUMENT_LIMIT = 100 * 1024 * 1024


def _read_upload(file_obj) -> bytes:
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except Exception:
            pass
    data = file_obj.read() if hasattr(file_obj, "read") else file_obj
    if isinstance(data, memoryview):
        data = data.tobytes()
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, (bytes, bytearray)):
        raise RuntimeError("Could not read the file.")
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except Exception:
            pass
    return bytes(data)


def _graph_error_message(data: dict, fallback: str) -> str:
    error = (data or {}).get("error") or {}
    details = ""
    if isinstance(error.get("error_data"), dict):
        details = error.get("error_data", {}).get("details") or ""
    return error.get("error_user_msg") or details or error.get("message") or fallback


def guess_media_type(content_type: str, filename: str) -> str:
    mime = (content_type or "").lower().split(";")[0].strip()
    name = (filename or "").lower()
    if mime in ("image/heic", "image/heif", "image/tiff") or name.endswith((".heic", ".heif", ".tiff", ".tif")):
        return "image"
    if mime.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return "image"
    if mime.startswith("video/") or name.endswith((".mp4", ".3gp", ".mov")):
        return "video"
    if mime.startswith("audio/") or name.endswith((".ogg", ".mp3", ".m4a", ".amr", ".aac", ".opus")):
        return "audio"
    return "document"


def prepare_whatsapp_media(file_obj, filename: str, content_type: str) -> tuple[bytes, str, str, str]:
    """Returns (bytes, filename, mime, wa_type) ready for Cloud API."""
    from io import BytesIO
    from PIL import Image

    raw = _read_upload(file_obj)
    if not raw:
        raise RuntimeError("The file was empty.")
    wa_type = guess_media_type(content_type, filename)
    mime = (content_type or "").lower().split(";")[0].strip() or "application/octet-stream"
    name = filename or "file"

    if wa_type == "image":
        try:
            image = Image.open(BytesIO(raw))
            if image.mode != "RGB":
                image = image.convert("RGB")
            quality = 85
            buf = BytesIO()
            image.save(buf, format="JPEG", quality=quality, optimize=True)
            while buf.tell() > IMAGE_LIMIT and quality > 40:
                quality -= 10
                buf = BytesIO()
                image.save(buf, format="JPEG", quality=quality, optimize=True)
            raw = buf.getvalue()
            name = (name.rsplit(".", 1)[0] or "photo") + ".jpg"
            mime = "image/jpeg"
        except Exception as exc:
            log.warning("Could not convert WhatsApp image: %s", exc)
            if mime not in ("image/jpeg", "image/png") and not name.lower().endswith((".jpg", ".jpeg", ".png")):
                raise RuntimeError("Send a JPG or PNG photo.") from exc
        if len(raw) > IMAGE_LIMIT:
            raise RuntimeError("Photo is too large. Send a smaller image.")
    elif wa_type == "audio":
        if mime.startswith("audio/webm") or name.endswith(".webm"):
            raise RuntimeError("Voice notes from this browser are not supported. Send a photo, video, or document.")
        if len(raw) > AUDIO_LIMIT:
            raise RuntimeError("Audio file is too large.")
    elif wa_type == "video":
        if name.endswith(".mov") or mime in ("video/quicktime",):
            raise RuntimeError("Send the video as MP4.")
        if len(raw) > VIDEO_LIMIT:
            raise RuntimeError("Video is too large. Send a shorter clip.")
        mime = mime if mime in ("video/mp4", "video/3gpp") else "video/mp4"
    else:
        if len(raw) > DOCUMENT_LIMIT:
            raise RuntimeError("Document is too large.")
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp")):
            return prepare_whatsapp_media(BytesIO(raw), name, "image/jpeg")
    return raw, name, mime, wa_type


def upload_graph_media(raw: bytes, filename: str, content_type: str) -> str:
    from io import BytesIO
    mime = content_type or "application/octet-stream"
    response = requests.post(
        graph_url(f"{phone_number_id()}/media"),
        headers={"Authorization": f"Bearer {graph_token()}"},
        files={
            "file": (filename or "file", BytesIO(raw), mime),
            "messaging_product": (None, "whatsapp"),
            "type": (None, mime),
        },
        timeout=90,
    )
    data = response.json() if response.content else {}
    if not response.ok:
        log.warning("WhatsApp media upload failed: %s", data)
        raise RuntimeError(_graph_error_message(data, "Could not upload this file to WhatsApp."))
    media_id = data.get("id")
    if not media_id:
        raise RuntimeError("WhatsApp did not accept the file.")
    return str(media_id)


EXPIRED_MEDIA_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="280" height="180" viewBox="0 0 280 180" fill="none">'
    '<rect width="280" height="180" rx="10" fill="#182229"/>'
    '<circle cx="140" cy="70" r="28" fill="#202C33" stroke="#8696A0" stroke-width="1.5" stroke-dasharray="3 3"/>'
    '<path d="M140 56v16l10 6" stroke="#8696A0" stroke-width="2" stroke-linecap="round"/>'
    '<text x="140" y="125" fill="#E9EDEF" font-family="system-ui, -apple-system, sans-serif" font-size="13" font-weight="600" text-anchor="middle">Media expired</text>'
    '<text x="140" y="145" fill="#8696A0" font-family="system-ui, -apple-system, sans-serif" font-size="11" text-anchor="middle">WhatsApp retains files for 30 days</text>'
    '</svg>'
).encode("utf-8")


def _local_media_dir() -> Path:
    media_dir = Path(settings.MEDIA_ROOT) / "whatsapp"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


def _find_cached_media(media_id: str) -> Optional[tuple[bytes, str, str]]:
    if not media_id:
        return None
    try:
        media_dir = _local_media_dir()
        for f in media_dir.glob(f"{media_id}.*"):
            if f.is_file() and f.stat().st_size > 0:
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                return f.read_bytes(), mime, f.name
    except Exception as exc:
        log.warning("Failed checking cached media %s: %s", media_id, exc)
    return None


def _save_cached_media(media_id: str, content: bytes, filename: str = "", mime: str = ""):
    if not media_id or not content:
        return
    try:
        media_dir = _local_media_dir()
        ext = ""
        if filename and "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()
        elif mime:
            ext = mimetypes.guess_extension(mime) or ""
        target = media_dir / f"{media_id}{ext}"
        if not target.exists():
            target.write_bytes(content)
    except Exception as exc:
        log.warning("Failed caching media %s: %s", media_id, exc)


def send_media_message(contact: WhatsAppContact, file_obj, filename: str, content_type: str, caption: str = "", sent_by=None) -> WhatsAppMessage:
    if not is_configured():
        raise RuntimeError("WhatsApp Cloud API is not configured.")
    if not has_open_session(contact):
        raise RuntimeError("Customer service window expired. Send an approved template first.")
    raw, filename, content_type, wa_type = prepare_whatsapp_media(file_obj, filename or "file", content_type or "")
    body_text = (caption or "").strip()
    preview = body_text or {
        "image": "Photo",
        "video": "Video",
        "audio": "Voice message",
        "document": filename or "Document",
    }.get(wa_type, "Attachment")
    media_id = upload_graph_media(raw, filename, content_type)
    _save_cached_media(media_id, raw, filename, content_type)
    message = _store_outgoing(contact, preview, wa_type, sent_by)
    message.media_id = media_id
    message.save(update_fields=["media_id"])
    payload_body = {"id": media_id}
    if body_text and wa_type in ("image", "video", "document"):
        payload_body["caption"] = body_text[:1024]
    if wa_type == "document":
        payload_body["filename"] = filename or "file"
    try:
        response = _post_messages({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": contact.wa_id,
            "type": wa_type,
            wa_type: payload_body,
        })
    except RuntimeError as exc:
        message.status = "failed"
        message.error_message = str(exc)
        message.save(update_fields=["status", "error_message"])
        raise
    return _apply_graph_response(message, contact, response)


def download_media(media_id: str) -> tuple[bytes, str, str]:
    if not media_id:
        raise ValueError("No media on this message")

    cached = _find_cached_media(media_id)
    if cached:
        return cached

    headers = {"Authorization": f"Bearer {graph_token()}"}
    try:
        meta = requests.get(graph_url(media_id), headers=headers, timeout=20)
        data = meta.json() if meta.content else {}
    except Exception as exc:
        log.warning("Network error contacting WhatsApp for media %s: %s", media_id, exc)
        return EXPIRED_MEDIA_SVG, "image/svg+xml", f"expired_{media_id}.svg"

    if not meta.ok:
        error = data.get("error") or {}
        msg = error.get("message") or ""
        code = error.get("code")
        # Media expired or removed by Meta (code 100, "does not exist", "unsupported get")
        if code == 100 or "does not exist" in msg.lower() or "unsupported get" in msg.lower():
            return EXPIRED_MEDIA_SVG, "image/svg+xml", f"expired_{media_id}.svg"
        raise RuntimeError(msg or "Could not load WhatsApp media")

    url = data.get("url")
    mime = data.get("mime_type") or "application/octet-stream"
    if not url:
        return EXPIRED_MEDIA_SVG, "image/svg+xml", f"expired_{media_id}.svg"

    try:
        raw = requests.get(url, headers=headers, timeout=60)
    except Exception as exc:
        log.warning("Network error downloading WhatsApp media %s: %s", media_id, exc)
        return EXPIRED_MEDIA_SVG, "image/svg+xml", f"expired_{media_id}.svg"

    if not raw.ok:
        if raw.status_code in (404, 410):
            return EXPIRED_MEDIA_SVG, "image/svg+xml", f"expired_{media_id}.svg"
        raise RuntimeError("Could not download WhatsApp media")

    _save_cached_media(media_id, raw.content, media_id, mime)
    return raw.content, mime, media_id


def send_template_message(contact: WhatsAppContact, name: str, language: str, body_params=None, sent_by=None, preview="") -> WhatsAppMessage:
    text = preview or f"Template: {name}"
    if body_params:
        text = body_params[0]
    message = _store_outgoing(contact, text, "template", sent_by)
    template = {
        "name": name,
        "language": {"code": language},
    }
    if body_params:
        template["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)[:1024]} for p in body_params],
        }]
    try:
        response = _post_messages({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": contact.wa_id,
            "type": "template",
            "template": template,
        })
    except RuntimeError as exc:
        message.status = "failed"
        message.error_message = str(exc)
        message.save(update_fields=["status", "error_message"])
        raise
    return _apply_graph_response(message, contact, response)


def send_text_message(to: str, text: str, sent_by=None, account=None) -> WhatsAppMessage:
    if not is_configured():
        raise RuntimeError("WhatsApp Cloud API is not configured. Add WHATSAPP_ACCESS_TOKEN on the server.")

    wa_id = normalize_wa_id(to)
    if not wa_id:
        raise ValueError("Enter a valid WhatsApp number.")
    body = (text or "").strip()
    if not body:
        raise ValueError("Message cannot be empty.")

    contact = get_or_create_contact(wa_id, account=account)
    if has_open_session(contact):
        return send_session_text(contact, body, sent_by=sent_by)
    try:
        name, language, uses_body = pick_start_template()
        return send_template_message(
            contact,
            name,
            language,
            body_params=[body] if uses_body else None,
            sent_by=sent_by,
            preview=body,
        )
    except RuntimeError as exc:
        raise friendly_send_error(exc) from exc


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
            graph_url(f"{phone_number_id()}/messages"),
            headers=graph_headers(),
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": last_inbound.wamid,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        log.warning("Could not mark WhatsApp message as read: %s", exc)


def meta_app_id() -> str:
    return getattr(settings, "META_APP_ID", "") or "1621336619429207"


def meta_app_secret() -> str:
    return getattr(settings, "META_APP_SECRET", "") or getattr(settings, "WHATSAPP_APP_SECRET", "") or ""


def meta_config_id() -> str:
    return getattr(settings, "META_EMBEDDED_SIGNUP_CONFIG_ID", "") or ""


def exchange_embedded_code(code: str) -> str:
    secret = meta_app_secret()
    if not secret:
        raise RuntimeError("Add META_APP_SECRET (Meta App Secret) on the server to finish Connect WhatsApp.")
    response = requests.get(
        graph_url("oauth/access_token"),
        params={
            "client_id": meta_app_id(),
            "client_secret": secret,
            "code": code,
        },
        timeout=20,
    )
    data = response.json() if response.content else {}
    token = data.get("access_token")
    if not token:
        err = (data.get("error") or {}).get("message") or response.text[:300]
        raise RuntimeError(err)
    return token


def complete_embedded_signup(code: str, session: dict, connected_by=None, crm_business_id=None) -> WhatsAppAccount:
    token = exchange_embedded_code(code)
    client = MetaWhatsAppClient(token)
    data = session.get("data") if isinstance(session.get("data"), dict) else session
    waba = str(data.get("waba_id") or data.get("wabaId") or waba_id())
    phone_id = str(data.get("phone_number_id") or data.get("phoneNumberId") or "")
    business_id = str(data.get("business_id") or data.get("businessId") or "")

    if not phone_id and waba:
        numbers = client.list_phone_numbers(waba)
        phone_id = str((numbers[0] or {}).get("id") or "") if numbers else ""

    if not phone_id:
        raise RuntimeError("Meta did not return a WhatsApp phone number. Complete Embedded Signup again.")

    phone_data = client.get_phone_number(phone_id)
    pin = getattr(settings, "WHATSAPP_REGISTER_PIN", "") or "000000"
    try:
        client.register_phone(phone_id, pin)
    except Exception:
        pass

    subscribed = False
    if waba:
        try:
            client.subscribe_webhooks(
                waba,
                "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
                settings.WHATSAPP_VERIFY_TOKEN,
            )
            subscribed = True
        except Exception as exc:
            log.warning("Could not subscribe WhatsApp webhooks: %s", exc)

    crm_business = None
    if crm_business_id:
        crm_business = WhatsAppBusiness.objects.filter(pk=crm_business_id).first()
    if not crm_business and business_id:
        crm_business = WhatsAppBusiness.objects.filter(meta_business_id=business_id).first()
    if not crm_business:
        crm_business = WhatsAppBusiness.objects.filter(is_default=True).first()
    if not crm_business:
        crm_business = WhatsAppBusiness.objects.create(
            name="Digital Product Solutions",
            slug="dps",
            is_default=True,
            meta_business_id=business_id,
            created_by=connected_by if getattr(connected_by, "is_authenticated", False) else None,
        )
    elif business_id and not crm_business.meta_business_id:
        crm_business.meta_business_id = business_id
        crm_business.save(update_fields=["meta_business_id", "updated_at"])

    platform = phone_data.get("platform_type") or WhatsAppAccount.PLATFORM_CLOUD
    is_on_biz = bool(phone_data.get("is_on_biz_app") or platform in ("NOT_APPLICABLE", "COEXISTENCE"))
    if is_on_biz:
        platform = WhatsAppAccount.PLATFORM_COEXISTENCE

    account = WhatsAppAccount.objects.filter(phone_number_id=phone_id).first()
    fields = dict(
        crm_business=crm_business,
        waba_id=waba,
        phone_number_id=phone_id,
        display_phone_number=phone_data.get("display_phone_number") or "",
        verified_name=phone_data.get("verified_name") or "",
        business_id=business_id,
        access_token=token,
        is_active=True,
        platform_type=platform if platform in dict(WhatsAppAccount.PLATFORM_CHOICES) else WhatsAppAccount.PLATFORM_CLOUD,
        is_on_biz_app=is_on_biz,
        quality_rating=str(phone_data.get("quality_rating") or ""),
        messaging_limit_tier=str(phone_data.get("messaging_limit_tier") or ""),
        webhook_subscribed=subscribed,
        sync_status=WhatsAppAccount.SYNC_CONNECTED,
        disconnected_at=None,
        last_error="",
        connected_by=connected_by if getattr(connected_by, "is_authenticated", False) else None,
        raw_session=session or {},
    )
    if account:
        for key, value in fields.items():
            setattr(account, key, value)
        account.save()
    else:
        account = WhatsAppAccount.objects.create(**fields)

    WhatsAppPhoneNumber.objects.update_or_create(
        account=account,
        phone_number_id=phone_id,
        defaults={
            "display_phone_number": account.display_phone_number,
            "verified_name": account.verified_name,
            "quality_rating": account.quality_rating,
            "messaging_limit_tier": account.messaging_limit_tier,
            "platform_type": account.platform_type,
            "is_on_biz_app": account.is_on_biz_app,
            "is_default": True,
        },
    )
    sync_templates(account)
    return account


def sync_templates(account: WhatsAppAccount) -> list:
    if not account or not (account.access_token or settings.WHATSAPP_ACCESS_TOKEN) or not account.waba_id:
        return []
    client = MetaWhatsAppClient(account.access_token or settings.WHATSAPP_ACCESS_TOKEN)
    rows = client.get_templates(account.waba_id)
    saved = []
    for item in rows:
        obj, _ = WhatsAppTemplate.objects.update_or_create(
            account=account,
            name=item.get("name") or "",
            language=item.get("language") or "en",
            defaults={
                "meta_id": str(item.get("id") or ""),
                "category": item.get("category") or "",
                "status": item.get("status") or "",
                "components": item.get("components") or [],
            },
        )
        saved.append(obj)
    account.last_sync_at = datetime.now(timezone.utc)
    account.save(update_fields=["last_sync_at", "updated_at"])
    WhatsAppSyncLog.objects.create(account=account, kind="templates", status="ok", finished_at=datetime.now(timezone.utc), detail=f"{len(saved)} templates")
    return saved
