from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification, SystemNotificationSetting
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Return only the current user's notifications
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        # Limit to latest 50 notifications on list
        queryset = self.filter_queryset(self.get_queryset())[:50]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # PATCH or POST /api/notifications/{id}/read/
    @action(detail=True, methods=['patch', 'post'], url_path='read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    # POST /api/notifications/mark-all-read/
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "All notifications marked as read."}, status=status.HTTP_200_OK)

    # GET /api/notifications/unread-count/
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})

    # GET /api/notifications/automation-status/
    @action(detail=False, methods=['get'], url_path='automation-status')
    def automation_status(self, request):
        setting = SystemNotificationSetting.get_settings()
        updater_name = None
        if setting.updated_by:
            updater_name = setting.updated_by.full_name or setting.updated_by.email
        return Response({
            "email_automation_enabled": setting.email_automation_enabled,
            "note": setting.email_automation_disabled_reason if not setting.email_automation_enabled else "",
            "updated_at": setting.updated_at,
            "updated_by": updater_name,
            "can_toggle": request.user.role in ['superadmin', 'admin', 'manager']
        })

    # POST /api/notifications/toggle-automation/
    @action(detail=False, methods=['post'], url_path='toggle-automation')
    def toggle_automation(self, request):
        if request.user.role not in ['superadmin', 'admin', 'manager']:
            return Response(
                {"detail": "Only administrators and managers can toggle email automation."},
                status=status.HTTP_403_FORBIDDEN
            )
        setting = SystemNotificationSetting.get_settings()
        enabled = request.data.get('enabled')
        if enabled is None:
            enabled = not setting.email_automation_enabled
        else:
            enabled = bool(enabled)

        setting.email_automation_enabled = enabled
        if not enabled:
            reason = request.data.get('reason')
            setting.email_automation_disabled_reason = reason.strip() if reason and reason.strip() else "Turned off by Administrator"
        setting.updated_by = request.user
        setting.save()

        status_str = "ENABLED" if enabled else "TURNED OFF"
        updater_name = request.user.full_name or request.user.email
        return Response({
            "email_automation_enabled": setting.email_automation_enabled,
            "note": setting.email_automation_disabled_reason if not setting.email_automation_enabled else "",
            "updated_at": setting.updated_at,
            "updated_by": updater_name,
            "can_toggle": True,
            "detail": f"Email automation has been {status_str}."
        })
