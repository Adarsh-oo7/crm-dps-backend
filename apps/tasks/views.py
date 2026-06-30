from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import Task, TaskChecklistItem, TaskComment, TaskTimeLog, TaskAttachment
from .serializers import (
    TaskSerializer, TaskChecklistItemSerializer, TaskCommentSerializer,
    TaskTimeLogSerializer, TaskAttachmentSerializer
)

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().order_by('order', '-created_at')
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['status', 'priority', 'task_type', 'project', 'client', 'assigned_to']
    search_fields = ['title', 'description']
    ordering_fields = ['order', 'created_at', 'due_date', 'priority']

    # GET /api/tasks/my-tasks/
    @action(detail=False, methods=['get'], url_path='my-tasks')
    def my_tasks(self, request):
        user = request.user
        tasks = self.filter_queryset(self.get_queryset().filter(assigned_to=user))
        stages = [choice[0] for choice in Task.STATUS_CHOICES]
        
        grouped_tasks = {}
        for stage in stages:
            stage_tasks = tasks.filter(status=stage)
            grouped_tasks[stage] = TaskSerializer(stage_tasks, many=True, context={'request': request}).data
            
        return Response(grouped_tasks)

    # GET /api/tasks/overdue/
    @action(detail=False, methods=['get'], url_path='overdue')
    def overdue(self, request):
        now = timezone.now()
        tasks = self.filter_queryset(self.get_queryset().filter(
            ~Q(status='Done') & ~Q(status='Cancelled') & Q(due_date__lt=now)
        ))
        return Response(TaskSerializer(tasks, many=True, context={'request': request}).data)

    # GET /api/tasks/today/
    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        tasks = self.filter_queryset(self.get_queryset().filter(
            due_date__range=(today_start, today_end)
        ))
        return Response(TaskSerializer(tasks, many=True, context={'request': request}).data)

    def check_status_update_permission(self, request, task, new_status):
        if task.status == new_status:
            return True
        is_assignee = task.assigned_to == request.user
        is_creator = task.created_by == request.user
        is_assigner = task.assigned_by == request.user
        is_management = request.user.role in ['superadmin', 'admin', 'manager']
        return is_assignee or is_creator or is_assigner or is_management

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        new_status = request.data.get('status')
        if new_status and new_status != instance.status:
            if not self.check_status_update_permission(request, instance, new_status):
                return Response(
                    {"detail": "You do not have permission to change this task status directly. You must request permission."},
                    status=status.HTTP_403_FORBIDDEN
                )
        return super().update(request, *args, **kwargs)

    # PATCH /api/tasks/{id}/status/
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        task = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response({"error": "status field is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not self.check_status_update_permission(request, task, new_status):
            return Response(
                {"detail": "You do not have permission to change this task status directly. You must request permission."},
                status=status.HTTP_403_FORBIDDEN
            )

        task.status = new_status
        if new_status == 'Done':
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        task.save()
        return Response(TaskSerializer(task, context={'request': request}).data)

    # POST /api/tasks/{id}/start-timer/
    @action(detail=True, methods=['post'], url_path='start-timer')
    def start_timer(self, request, pk=None):
        task = self.get_object()
        now = timezone.now()
        
        # Stop any active timers for the current user
        active_logs = TaskTimeLog.objects.filter(user=request.user, ended_at__isnull=True)
        for log in active_logs:
            log.ended_at = now
            if not log.description:
                log.description = "Auto-stopped for new timer start"
            log.save()
            
        # Create a new active timer
        new_log = TaskTimeLog.objects.create(
            task=task,
            user=request.user,
            started_at=now,
            description=""
        )
        
        # Auto-update status to In Progress if it is Todo
        if task.status == 'Todo':
            task.status = 'In Progress'
            task.save()
            
        return Response(TaskTimeLogSerializer(new_log).data, status=status.HTTP_201_CREATED)

    # POST /api/tasks/{id}/stop-timer/
    @action(detail=True, methods=['post'], url_path='stop-timer')
    def stop_timer(self, request, pk=None):
        task = self.get_object()
        active_log = TaskTimeLog.objects.filter(task=task, user=request.user, ended_at__isnull=True).first()
        if not active_log:
            return Response({"error": "No active timer running for this task"}, status=status.HTTP_400_BAD_REQUEST)
            
        active_log.ended_at = timezone.now()
        description = request.data.get('description', '')
        if description:
            active_log.description = description
        active_log.save()
        return Response(TaskTimeLogSerializer(active_log).data, status=status.HTTP_200_OK)

    # GET /api/tasks/active-timer/
    @action(detail=False, methods=['get'], url_path='active-timer')
    def active_timer(self, request):
        active_log = TaskTimeLog.objects.filter(user=request.user, ended_at__isnull=True).first()
        if active_log:
            return Response(TaskTimeLogSerializer(active_log).data)
        return Response(None, status=status.HTTP_204_NO_CONTENT)

    # POST /api/tasks/{id}/request-status-change/
    @action(detail=True, methods=['post'], url_path='request-status-change')
    def request_status_change(self, request, pk=None):
        task = self.get_object()
        requested_status = request.data.get('requested_status')
        if not requested_status:
            return Response({"error": "requested_status is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Create comment in task
        user_name = request.user.full_name or request.user.email
        comment_text = f"[System] {user_name} requested to change task status from '{task.status}' to '{requested_status}'."
        TaskComment.objects.create(
            task=task,
            user=request.user,
            comment=comment_text
        )
        
        # Find who to notify
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipients = list(User.objects.filter(role__in=['superadmin', 'admin', 'manager']))
        if task.assigned_to and task.assigned_to not in recipients:
            recipients.append(task.assigned_to)
            
        recipients = [r for r in recipients if r != request.user]
        
        from apps.notifications.models import Notification
        for recipient in recipients:
            Notification.objects.create(
                user=recipient,
                title="Status Change Requested",
                message=f"{user_name} requested status change for task '{task.title}' to '{requested_status}'.",
                notification_type="Task",
                related_url="/tasks"
            )
            
        return Response({"detail": "Status change request sent successfully"}, status=status.HTTP_200_OK)

    # POST /api/tasks/{id}/checklist/
    @action(detail=True, methods=['post'], url_path='checklist')
    def checklist(self, request, pk=None):
        task = self.get_object()
        serializer = TaskChecklistItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(task=task)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # PATCH /api/tasks/{id}/checklist/{cid}/
    @action(detail=True, methods=['patch'], url_path=r'checklist/(?P<cid>\d+)')
    def checklist_detail(self, request, pk=None, cid=None):
        task = self.get_object()
        item = get_object_or_404(TaskChecklistItem, id=cid, task=task)
        item.is_completed = request.data.get('is_completed', item.is_completed)
        item.save()
        return Response(TaskChecklistItemSerializer(item).data)

    # GET/POST /api/tasks/{id}/comments/
    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        task = self.get_object()
        if request.method == 'GET':
            comments = task.comments.all().order_by('-created_at')
            return Response(TaskCommentSerializer(comments, many=True).data)
            
        elif request.method == 'POST':
            serializer = TaskCommentSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(task=task, user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # POST /api/tasks/{id}/attachments/
    @action(detail=True, methods=['post'], url_path='attachments')
    def attachments(self, request, pk=None):
        task = self.get_object()
        serializer = TaskAttachmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(task=task, uploaded_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # GET/POST /api/tasks/{id}/timelogs/
    @action(detail=True, methods=['get', 'post'], url_path='timelogs')
    def timelogs(self, request, pk=None):
        task = self.get_object()
        if request.method == 'GET':
            logs = task.timelogs.all().order_by('-created_at')
            return Response(TaskTimeLogSerializer(logs, many=True).data)
            
        elif request.method == 'POST':
            serializer = TaskTimeLogSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(task=task, user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
