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

    # PATCH /api/tasks/{id}/status/
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        task = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response({"error": "status field is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        task.status = new_status
        if new_status == 'Done':
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        task.save()
        return Response(TaskSerializer(task, context={'request': request}).data)

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
