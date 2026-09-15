from django.db.models import Q, Sum
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.conf import settings

from .models import WhatsAppContact
from .serializers import WhatsAppContactSerializer, WhatsAppMessageSerializer
from .services import ingest_webhook, is_configured, mark_contact_read, send_text_message


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

    ingest_webhook(request.data if isinstance(request.data, dict) else {})
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def connection_status(request):
    return Response({
        "configured": is_configured(),
        "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
        "display_number": settings.WHATSAPP_DISPLAY_NUMBER,
        "webhook_url": "https://crm-api.digitalproductsolutions.in/api/whatsapp/webhook/",
        "verify_token_set": bool(settings.WHATSAPP_VERIFY_TOKEN),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    total = WhatsAppContact.objects.aggregate(total=Sum("unread_count"))["total"] or 0
    return Response({"unread_count": total})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations(request):
    qs = WhatsAppContact.objects.all()
    q = (request.query_params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(profile_name__icontains=q) | Q(wa_id__icontains=q))
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
    return Response({
        "contact": WhatsAppContactSerializer(message.contact).data,
        "message": WhatsAppMessageSerializer(message).data,
    }, status=status.HTTP_201_CREATED)
