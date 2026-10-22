import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Exists, OuterRef, Q, Sum
from django.http import HttpResponse
from django.utils import timezone as dj_timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .models import WhatsAppContact, WhatsAppMessage
from .serializers import WhatsAppContactSerializer, WhatsAppMessageSerializer
from .services import (
    BILLING_URL,
    business_profile,
    complete_embedded_signup,
    display_number,
    download_media,
    has_open_session,
    is_configured,
    last_webhook_at,
    list_templates,
    mark_contact_read,
    merge_duplicate_contacts,
    meta_app_id,
    meta_config_id,
    normalize_wa_id,
    phone_number_id,
    process_webhook_payload,
    prune_noise_contacts,
    send_media_message,
    send_template_message,
    send_text_message,
    verify_webhook_signature,
    waba_id,
)
from .access import get_account_for_user, user_can_access_account, visible_accounts

log = logging.getLogger(__name__)


class WhatsAppSendThrottle(UserRateThrottle):
    scope = "whatsapp_send"


@csrf_exempt
@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def webhook(request):
    if request.method == "GET":
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")
        if mode == "subscribe" and token and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)

    if not verify_webhook_signature(request.body, request.headers.get("X-Hub-Signature-256", "")):
        log.warning("WhatsApp webhook signature mismatch")
        return HttpResponse("Forbidden", status=403)

    payload = request.data if isinstance(request.data, dict) else {}
    if not payload:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            payload = {}
    try:
        process_webhook_payload(payload, request.body)
    except Exception:
        log.exception("WhatsApp webhook ingest failed")
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def connection_status(request):
    account = get_account_for_user(request.user)
    allowed = visible_accounts(request.user)
    inbound = WhatsAppMessage.objects.filter(Q(account__in=allowed) | Q(account__isnull=True), direction="in").count()
    last_fail = (
        WhatsAppMessage.objects.filter(Q(account__in=allowed) | Q(account__isnull=True), direction="out", status="failed")
        .order_by("-id")
        .first()
    )
    billing_blocked = bool(
        last_fail and last_fail.error_message and "payment" in last_fail.error_message.lower()
    )
    profile = business_profile()
    return Response({
        "configured": is_configured(),
        "phone_number_id": account.phone_number_id if account else phone_number_id(),
        "display_number": account.display_phone_number if account else display_number(),
        "waba_id": account.waba_id if account else waba_id(),
        "verified_name": (account.verified_name if account else "") or profile.get("verified_name") or "",
        "profile_picture_url": profile.get("profile_picture_url") or "",
        "about": profile.get("about") or "",
        "webhook_url": "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
        "verify_token_set": bool(settings.WHATSAPP_VERIFY_TOKEN),
        "last_webhook_at": account.last_webhook_at if account else last_webhook_at(),
        "inbound_count": inbound,
        "free_mode": True,
        "click_to_chat_url": f"https://wa.me/{''.join(ch for ch in (account.display_phone_number if account else display_number()) if ch.isdigit())}",
        "billing_blocked": billing_blocked,
        "billing_url": BILLING_URL,
        "last_error": (last_fail.error_message if last_fail else "") or "",
        "platform_label": account.platform_label if account else "",
        "is_on_biz_app": bool(account and account.is_on_biz_app),
        "sync_status": account.sync_status if account else "disconnected",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration(request):
    account = get_account_for_user(request.user)
    allowed = visible_accounts(request.user)
    inbound = WhatsAppMessage.objects.filter(Q(account__in=allowed) | Q(account__isnull=True), direction="in").count()
    return Response({
        "connected": bool(account and account.is_active),
        "display_number": account.display_phone_number if account else display_number(),
        "phone_number_id": account.phone_number_id if account else phone_number_id(),
        "waba_id": account.waba_id if account else waba_id(),
        "verified_name": (account.verified_name if account else "Digital Product Solutions"),
        "connected_at": account.connected_at.isoformat() if account else "",
        "source": "embedded_signup" if account else "server",
        "meta_app_id": meta_app_id(),
        "meta_config_id": meta_config_id(),
        "signup_ready": bool(meta_app_id() and meta_config_id()),
        "webhook_url": "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
        "click_to_chat_url": f"https://wa.me/{''.join(ch for ch in (account.display_phone_number if account else display_number()) if ch.isdigit())}",
        "inbound_count": inbound,
        "inbox_url": "/whatsapp",
        "billing_url": BILLING_URL,
        "can_message_first": True,
        "business_id": account.crm_business_id if account else None,
        "platform_label": account.platform_label if account else "",
        "is_on_biz_app": bool(account and account.is_on_biz_app),
        "sync_status": account.sync_status if account else "disconnected",
        "quality_rating": account.quality_rating if account else "",
        "messaging_limit_tier": account.messaging_limit_tier if account else "",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def connect_whatsapp(request):
    code = (request.data.get("code") or "").strip()
    session = request.data.get("session") or {}
    if not code:
        return Response({"detail": "Meta did not return an authorization code."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        account = complete_embedded_signup(
            code,
            session if isinstance(session, dict) else {},
            connected_by=request.user,
            crm_business_id=request.data.get("business_id"),
        )
    except RuntimeError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "connected": True,
        "display_number": account.display_phone_number,
        "phone_number_id": account.phone_number_id,
        "waba_id": account.waba_id,
        "verified_name": account.verified_name,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def disconnect_whatsapp(request):
    from django.utils import timezone
    from .models import WhatsAppAccount as Account
    account = get_account_for_user(request.user, request.data.get("account_id"))
    if not account:
        return Response({"detail": "WhatsApp account not found."}, status=status.HTTP_404_NOT_FOUND)
    account.is_active = False
    account.sync_status = Account.SYNC_DISCONNECTED
    account.disconnected_at = timezone.now()
    account.access_token = ""
    account.save(update_fields=["is_active", "sync_status", "disconnected_at", "access_token", "updated_at"])
    return Response({"connected": False, "history_preserved": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def templates(request):
    return Response(list_templates())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    total = WhatsAppContact.objects.filter(
        Q(account__in=visible_accounts(request.user)) | Q(account__isnull=True)
    ).aggregate(total=Sum("unread_count"))["total"] or 0
    return Response({"unread_count": total})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations(request):
    merge_duplicate_contacts()
    prune_noise_contacts()
    allowed = visible_accounts(request.user)
    qs = WhatsAppContact.objects.all()
    account_id = request.query_params.get("account_id")
    if account_id:
        account = get_account_for_user(request.user, account_id)
        qs = qs.filter(Q(account=account) | Q(account__isnull=True)) if account else qs.none()
    else:
        qs = qs.filter(Q(account__in=allowed) | Q(account__isnull=True))
    own = normalize_wa_id(display_number())
    if own:
        qs = qs.exclude(wa_id=own)
    has_content = WhatsAppMessage.objects.filter(contact_id=OuterRef("pk")).filter(
        ~Q(text="") | ~Q(media_id="")
    )
    recent_in = WhatsAppMessage.objects.filter(
        contact_id=OuterRef("pk"),
        direction="in",
        timestamp__gte=dj_timezone.now() - timedelta(hours=24),
    )
    qs = qs.annotate(has_content=Exists(has_content), has_recent_in=Exists(recent_in)).filter(has_content=True)
    q = (request.query_params.get("q") or "").strip()
    digits = "".join(ch for ch in q if ch.isdigit())
    if q:
        query = Q(profile_name__icontains=q) | Q(wa_id__icontains=q)
        if digits:
            query |= Q(wa_id__icontains=digits)
            query |= Q(wa_id__endswith=digits[-10:])
        qs = qs.filter(query)
    qs = qs.order_by("-has_recent_in", "-last_message_at", "-updated_at")
    return Response(WhatsAppContactSerializer(qs[:200], many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([WhatsAppSendThrottle])
def conversation_detail(request, pk):
    try:
        contact = WhatsAppContact.objects.get(pk=pk)
    except WhatsAppContact.DoesNotExist:
        return Response({"detail": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)
    if contact.account_id and not user_can_access_account(request.user, contact.account):
        return Response({"detail": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        mark_contact_read(contact)
        contact.refresh_from_db()
        messages = contact.messages.all().order_by("timestamp", "id")[:500]
        return Response({
            "contact": WhatsAppContactSerializer(contact).data,
            "messages": WhatsAppMessageSerializer(messages, many=True).data,
            "session_open": has_open_session(contact),
        })

    if not has_open_session(contact):
        name = (request.data.get("template_name") or request.data.get("name") or "").strip()
        if not name:
            return Response(
                {
                    "detail": "Customer service window expired. Select an approved template.",
                    "session_open": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            message = send_template_message(
                contact,
                name,
                request.data.get("language") or "en",
                body_params=[request.data.get("text")] if request.data.get("text") else None,
                sent_by=request.user,
                preview=request.data.get("text") or name,
            )
        except (ValueError, RuntimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    try:
        message = send_text_message(contact.wa_id, request.data.get("text", ""), sent_by=request.user, account=contact.account)
    except (ValueError, RuntimeError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
@throttle_classes([WhatsAppSendThrottle])
def conversation_media(request, pk):
    try:
        contact = WhatsAppContact.objects.get(pk=pk)
    except WhatsAppContact.DoesNotExist:
        return Response({"detail": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)
    if contact.account_id and not user_can_access_account(request.user, contact.account):
        return Response({"detail": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)
    upload = request.FILES.get("file")
    if not upload:
        return Response({"detail": "Choose a photo, video, document or voice note."}, status=status.HTTP_400_BAD_REQUEST)
    caption = request.data.get("caption") or request.data.get("text") or ""
    log.info(
        "WhatsApp media upload: contact=%s name=%s type=%s size=%s",
        contact.pk,
        getattr(upload, "name", ""),
        getattr(upload, "content_type", ""),
        getattr(upload, "size", 0),
    )
    try:
        message = send_media_message(
            contact,
            upload,
            getattr(upload, "name", "file"),
            getattr(upload, "content_type", "") or "",
            caption=caption,
            sent_by=request.user,
        )
    except (ValueError, RuntimeError) as exc:
        log.warning("WhatsApp media send failed: %s", exc)
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        log.exception("WhatsApp media send crashed")
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def message_media(request, pk):
    try:
        message = WhatsAppMessage.objects.get(pk=pk)
    except WhatsAppMessage.DoesNotExist:
        return Response({"detail": "Message not found."}, status=status.HTTP_404_NOT_FOUND)
    if not message.media_id:
        return Response({"detail": "This message has no media."}, status=status.HTTP_404_NOT_FOUND)
    account = message.account or message.contact.account
    if account and not user_can_access_account(request.user, account):
        return Response({"detail": "Message not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        content, mime, filename = download_media(message.media_id)
    except Exception as exc:
        log.warning("Could not download WhatsApp media %s for message %s: %s", message.media_id, pk, exc)
        from .services import EXPIRED_MEDIA_SVG
        content, mime, filename = EXPIRED_MEDIA_SVG, "image/svg+xml", f"expired_{message.media_id}.svg"
    response = HttpResponse(content, content_type=mime)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "public, max-age=86400"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([WhatsAppSendThrottle])
def start_conversation(request):
    to = request.data.get("to") or request.data.get("phone") or ""
    text = request.data.get("text") or ""
    account = get_account_for_user(request.user, request.data.get("account_id"))
    try:
        message = send_text_message(to, text, sent_by=request.user, account=account)
    except (ValueError, RuntimeError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "contact": WhatsAppContactSerializer(message.contact).data,
        "message": WhatsAppMessageSerializer(message).data,
    }, status=status.HTTP_201_CREATED)
