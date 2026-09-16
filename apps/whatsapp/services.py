import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from .models import WhatsAppAccount, WhatsAppContact, WhatsAppMessage

log = logging.getLogger(__name__)

LAST_WEBHOOK_CACHE = "whatsapp:last_webhook_at"
SESSION_HOURS = 24
CUSTOM_TEMPLATE = "dps_chat_message"
CUSTOM_TEMPLATE_LANG = "en"
HELLO_TEMPLATE = "hello_world"
HELLO_TEMPLATE_LANG = "en_US"


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


def get_or_create_contact(wa_id: str, profile_name: str = "") -> WhatsAppContact:
    wa_id = normalize_wa_id(wa_id)
    contact = WhatsAppContact.objects.filter(wa_id=wa_id).first()
    if not contact and len(wa_id) >= 10:
        tail = wa_id[-10:]
        aliases = list(WhatsAppContact.objects.filter(wa_id__endswith=tail))
        if aliases:
            contact = next((row for row in aliases if row.wa_id == wa_id), aliases[0])
            if contact.wa_id != wa_id:
                existing = WhatsAppContact.objects.filter(wa_id=wa_id).first()
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
        contact = WhatsAppContact.objects.create(wa_id=wa_id)
    if len(wa_id) >= 10:
        tail = wa_id[-10:]
        for extra in WhatsAppContact.objects.filter(wa_id__endswith=tail).exclude(pk=contact.pk):
            extra.messages.update(contact=contact)
            extra.delete()
    if profile_name and contact.profile_name != profile_name:
        contact.profile_name = profile_name
        contact.save(update_fields=["profile_name", "updated_at"])
    return contact


def graph_url(path: str) -> str:
    version = getattr(settings, "WHATSAPP_GRAPH_VERSION", "v21.0")
    return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"


def active_account() -> Optional[WhatsAppAccount]:
    return WhatsAppAccount.objects.filter(is_active=True).order_by("-connected_at").first()


def graph_headers() -> dict:
    account = active_account()
    token = (account.access_token if account and account.access_token else settings.WHATSAPP_ACCESS_TOKEN)
    return {
        "Authorization": f"Bearer {token}",
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
    grouped: dict[str, list[WhatsAppContact]] = {}
    for contact in WhatsAppContact.objects.all():
        key = contact.wa_id[-10:] if len(contact.wa_id) >= 10 else contact.wa_id
        grouped.setdefault(key, []).append(contact)
    for rows in grouped.values():
        if not rows:
            continue
        preferred = max(rows, key=lambda row: (len(row.wa_id), row.messages.count(), row.id))
        canonical_id = normalize_wa_id(preferred.wa_id)
        if preferred.wa_id != canonical_id:
            clash = WhatsAppContact.objects.filter(wa_id=canonical_id).exclude(pk=preferred.pk).first()
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
        for change in (entry.get("changes") or []):
            value = change.get("value") or {}
            contacts = {c.get("wa_id"): c for c in (value.get("contacts") or []) if c.get("wa_id")}

            for msg in value.get("messages") or []:
                raw_from = msg.get("from", "")
                wa_id = normalize_wa_id(raw_from)
                if not wa_id:
                    continue
                profile_name = ""
                for cid, meta in contacts.items():
                    if normalize_wa_id(cid) == wa_id or cid == raw_from:
                        profile_name = (meta.get("profile") or {}).get("name", "")
                        break
                text, message_type, media_id = extract_message_text(msg)
                if message_type in SKIP_INBOUND_TYPES and not text:
                    continue
                if not text and message_type not in ("image", "video", "audio", "document", "sticker", "location", "contacts", "text", "button", "interactive"):
                    continue
                own = normalize_wa_id(display_number())
                if own and wa_id == own:
                    continue
                contact = get_or_create_contact(wa_id, profile_name)
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
                    err = errors[0] if isinstance(errors[0], dict) else {}
                    message.error_message = err.get("title") or err.get("message") or str(errors[0])
                    message.status = "failed"
                message.save(update_fields=["status", "error_message"])


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
    for item in list_templates():
        if item.get("name") == CUSTOM_TEMPLATE and item.get("status") == "APPROVED":
            return CUSTOM_TEMPLATE, item.get("language") or CUSTOM_TEMPLATE_LANG, True
    return HELLO_TEMPLATE, HELLO_TEMPLATE_LANG, False


def _store_outgoing(contact, text, message_type, sent_by) -> WhatsAppMessage:
    now = datetime.now(timezone.utc)
    return WhatsAppMessage.objects.create(
        contact=contact,
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
        error = data.get("error") or {}
        message.status = "failed"
        message.error_message = error.get("error_user_msg") or error.get("message") or response.text[:500]
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
    try:
        return send_session_text(contact, body, sent_by=sent_by)
    except RuntimeError as exc:
        detail = str(exc)
        lowered = detail.lower()
        window_closed = any(token in lowered for token in (
            "131047",
            "24 hour",
            "24-hour",
            "customer service window",
            "re-engagement",
            "outside the allowed window",
        ))
        if not window_closed:
            raise
        name, language, uses_body = pick_start_template()
        return send_template_message(
            contact,
            name,
            language,
            body_params=[body] if uses_body else None,
            sent_by=sent_by,
            preview=body if uses_body else body,
        )


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


def complete_embedded_signup(code: str, session: dict, connected_by=None) -> WhatsAppAccount:
    token = exchange_embedded_code(code)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = session.get("data") if isinstance(session.get("data"), dict) else session
    waba = str(data.get("waba_id") or data.get("wabaId") or waba_id())
    phone_id = str(data.get("phone_number_id") or data.get("phoneNumberId") or "")
    business_id = str(data.get("business_id") or data.get("businessId") or "")

    if not phone_id:
        numbers = requests.get(graph_url(f"{waba}/phone_numbers"), headers=headers, timeout=20)
        payload = numbers.json() if numbers.content else {}
        first = (payload.get("data") or [{}])[0]
        phone_id = str(first.get("id") or "")

    if not phone_id:
        raise RuntimeError("Meta did not return a WhatsApp phone number. Complete Embedded Signup again.")

    phone = requests.get(
        graph_url(phone_id),
        headers=headers,
        params={"fields": "id,display_phone_number,verified_name,quality_rating"},
        timeout=20,
    )
    phone_data = phone.json() if phone.content else {}

    pin = getattr(settings, "WHATSAPP_REGISTER_PIN", "") or "000000"
    try:
        requests.post(
            graph_url(f"{phone_id}/register"),
            headers=headers,
            json={"messaging_product": "whatsapp", "pin": pin},
            timeout=20,
        )
    except requests.RequestException:
        pass

    if waba:
        try:
            requests.post(
                graph_url(f"{waba}/subscribed_apps"),
                headers=headers,
                json={
                    "override_callback_uri": "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
                    "verify_token": settings.WHATSAPP_VERIFY_TOKEN,
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            log.warning("Could not subscribe WhatsApp webhooks: %s", exc)

    WhatsAppAccount.objects.filter(is_active=True).update(is_active=False)
    return WhatsAppAccount.objects.create(
        waba_id=waba,
        phone_number_id=phone_id,
        display_phone_number=phone_data.get("display_phone_number") or "",
        verified_name=phone_data.get("verified_name") or "",
        business_id=business_id,
        access_token=token,
        is_active=True,
        connected_by=connected_by if getattr(connected_by, "is_authenticated", False) else None,
        raw_session=session or {},
    )
