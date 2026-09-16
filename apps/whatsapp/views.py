import json
import logging

from django.conf import settings
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import WhatsAppAccount, WhatsAppContact, WhatsAppMessage
from .serializers import WhatsAppContactSerializer, WhatsAppMessageSerializer
from .services import (
    active_account,
    business_profile,
    complete_embedded_signup,
    display_number,
    ingest_webhook,
    is_configured,
    last_webhook_at,
    list_templates,
    mark_contact_read,
    merge_duplicate_contacts,
    meta_app_id,
    meta_config_id,
    normalize_wa_id,
    phone_number_id,
    prune_noise_contacts,
    send_text_message,
    waba_id,
)

log = logging.getLogger(__name__)


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

    payload = request.data if isinstance(request.data, dict) else {}
    if not payload:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            payload = {}
    try:
        ingest_webhook(payload)
    except Exception:
        log.exception("WhatsApp webhook ingest failed")
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def connection_status(request):
    inbound = WhatsAppMessage.objects.filter(direction="in").count()
    last_fail = (
        WhatsAppMessage.objects.filter(direction="out", status="failed")
        .order_by("-id")
        .first()
    )
    billing_blocked = bool(
        last_fail and last_fail.error_message and "payment" in last_fail.error_message.lower()
    )
    profile = business_profile()
    return Response({
        "configured": is_configured(),
        "phone_number_id": phone_number_id(),
        "display_number": display_number(),
        "waba_id": waba_id(),
        "verified_name": profile.get("verified_name") or "",
        "profile_picture_url": profile.get("profile_picture_url") or "",
        "about": profile.get("about") or "",
        "webhook_url": "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
        "verify_token_set": bool(settings.WHATSAPP_VERIFY_TOKEN),
        "last_webhook_at": last_webhook_at(),
        "inbound_count": inbound,
        "free_mode": True,
        "click_to_chat_url": f"https://wa.me/{''.join(ch for ch in display_number() if ch.isdigit())}",
        "billing_blocked": billing_blocked,
        "billing_url": "https://business.facebook.com/billing_hub/accounts/details/?business_id=622580630220380&asset_id=1619899406510846&wizard_name=ADD_PM&account_type=whatsapp-business-account",
        "last_error": (last_fail.error_message if last_fail else "") or "",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration(request):
    account = active_account()
    inbound = WhatsAppMessage.objects.filter(direction="in").count()
    return Response({
        "connected": is_configured(),
        "display_number": display_number(),
        "phone_number_id": phone_number_id(),
        "waba_id": waba_id(),
        "verified_name": (account.verified_name if account else "Digital Product Solutions"),
        "connected_at": account.connected_at.isoformat() if account else "",
        "source": "embedded_signup" if account else "server",
        "meta_app_id": meta_app_id(),
        "meta_config_id": meta_config_id(),
        "signup_ready": bool(meta_app_id() and meta_config_id()),
        "webhook_url": "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
        "click_to_chat_url": f"https://wa.me/{''.join(ch for ch in display_number() if ch.isdigit())}",
        "inbound_count": inbound,
        "inbox_url": "/whatsapp",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def connect_whatsapp(request):
    code = (request.data.get("code") or "").strip()
    session = request.data.get("session") or {}
    if not code:
        return Response({"detail": "Meta did not return an authorization code."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        account = complete_embedded_signup(code, session if isinstance(session, dict) else {}, connected_by=request.user)
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
    WhatsAppAccount.objects.filter(is_active=True).update(is_active=False)
    return Response({"connected": is_configured()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def templates(request):
    return Response(list_templates())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    total = WhatsAppContact.objects.aggregate(total=Sum("unread_count"))["total"] or 0
    return Response({"unread_count": total})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations(request):
    merge_duplicate_contacts()
    prune_noise_contacts()
    qs = WhatsAppContact.objects.all()
    own = normalize_wa_id(display_number())
    if own:
        qs = qs.exclude(wa_id=own)
    q = (request.query_params.get("q") or "").strip()
    digits = "".join(ch for ch in q if ch.isdigit())
    if q:
        query = Q(profile_name__icontains=q) | Q(wa_id__icontains=q)
        if digits:
            query |= Q(wa_id__icontains=digits)
            query |= Q(wa_id__endswith=digits[-10:])
        qs = qs.filter(query)
    return Response(WhatsAppContactSerializer(qs[:200], many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def conversation_detail(request, pk):
    try:
        contact = WhatsAppContact.objects.get(pk=pk)
    except WhatsAppContact.DoesNotExist:
        return Response({"detail": "Chat not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        mark_contact_read(contact)
        contact.refresh_from_db()
        messages = contact.messages.all().order_by("timestamp", "id")[:500]
        return Response({
            "contact": WhatsAppContactSerializer(contact).data,
            "messages": WhatsAppMessageSerializer(messages, many=True).data,
        })

    try:
        message = send_text_message(contact.wa_id, request.data.get("text", ""), sent_by=request.user)
    except (ValueError, RuntimeError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_conversation(request):
    to = request.data.get("to") or request.data.get("phone") or ""
    text = request.data.get("text") or ""
    try:
        message = send_text_message(to, text, sent_by=request.user)
    except (ValueError, RuntimeError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "contact": WhatsAppContactSerializer(message.contact).data,
        "message": WhatsAppMessageSerializer(message).data,
    }, status=status.HTTP_201_CREATED)
