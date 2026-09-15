from django.urls import path
from . import views

urlpatterns = [
    path("webhook/", views.webhook, name="whatsapp-webhook"),
    path("status/", views.connection_status, name="whatsapp-status"),
    path("unread-count/", views.unread_count, name="whatsapp-unread"),
    path("conversations/", views.conversations, name="whatsapp-conversations"),
    path("conversations/<int:pk>/", views.conversation_detail, name="whatsapp-conversation"),
    path("send/", views.start_conversation, name="whatsapp-send"),
]
