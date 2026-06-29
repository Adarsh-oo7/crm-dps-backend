from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from .models import Project, Milestone
from .serializers import ProjectSerializer, MilestoneSerializer
from apps.tasks.serializers import TaskSerializer # We will create tasks serializers next

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['status', 'project_type', 'client', 'project_manager']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'deadline', 'completion_percentage', 'budget']

    def perform_destroy(self, instance):
        # Soft delete: update status to Cancelled instead of deleting record
        instance.status = 'Cancelled'
        instance.save()

    # GET /api/projects/kanban/
    @action(detail=False, methods=['get'], url_path='kanban')
    def kanban(self, request):
        projects = self.filter_queryset(self.get_queryset())
        stages = [choice[0] for choice in Project.STATUS_CHOICES]
        
        kanban_data = {}
        for stage in stages:
            stage_projects = projects.filter(status=stage)
            kanban_data[stage] = ProjectSerializer(stage_projects, many=True, context={'request': request}).data
            
        return Response(kanban_data)

    # PATCH /api/projects/{id}/status/
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        project = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response({"error": "status field is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        project.status = new_status
        project.save()
        return Response(ProjectSerializer(project, context={'request': request}).data)

    # GET/POST /api/projects/{id}/milestones/
    @action(detail=True, methods=['get', 'post'], url_path='milestones')
    def milestones(self, request, pk=None):
        project = self.get_object()
        if request.method == 'GET':
            milestones = project.milestones.all().order_by('due_date')
            return Response(MilestoneSerializer(milestones, many=True).data)
            
        elif request.method == 'POST':
            serializer = MilestoneSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(project=project)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # PUT/DELETE /api/projects/{id}/milestones/{mid}/
    @action(detail=True, methods=['put', 'delete'], url_path=r'milestones/(?P<mid>\d+)')
    def milestone_detail(self, request, pk=None, mid=None):
        project = self.get_object()
        milestone = get_object_or_404(Milestone, id=mid, project=project)
        
        if request.method == 'PUT':
            serializer = MilestoneSerializer(milestone, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        elif request.method == 'DELETE':
            milestone.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    # GET /api/projects/{id}/tasks/
    @action(detail=True, methods=['get'], url_path='tasks')
    def tasks(self, request, pk=None):
        project = self.get_object()
        tasks = project.tasks.all().order_by('due_date')
        return Response(TaskSerializer(tasks, many=True, context={'request': request}).data)

    # GET /api/projects/{id}/timeline/
    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, pk=None):
        # Gather logs relevant to project
        # In a real setup, we could log state changes of milestones, tasks completed, etc.
        # Let's return basic timeline logs
        project = self.get_object()
        timeline_data = [
            {
                "type": "System",
                "action": "Project Created",
                "description": f"Project '{project.name}' was initialized.",
                "user": project.created_by.full_name if project.created_by else "System",
                "timestamp": project.created_at
            }
        ]
        
        # Add completed milestones to timeline
        for ms in project.milestones.filter(status='Completed'):
            timeline_data.append({
                "type": "Milestone",
                "action": "Milestone Completed",
                "description": f"Milestone '{ms.title}' was marked completed.",
                "user": ms.assigned_to.full_name if ms.assigned_to else "System",
                "timestamp": ms.completion_date or project.updated_at
            })
            
        timeline_data.sort(key=lambda x: x['timestamp'], reverse=True)
        return Response(timeline_data)

    # GET /api/projects/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        projects = self.filter_queryset(self.get_queryset())
        
        total_projects = projects.count()
        projects_by_status = projects.values('status').annotate(count=Count('id'))
        projects_by_type = projects.values('project_type').annotate(count=Count('id'))
        
        overdue_projects_count = projects.filter(
            ~Q(status='Completed') & ~Q(status='Cancelled') & Q(deadline__lt=models.functions.Now())
        ).count()
        
        return Response({
            "total_projects": total_projects,
            "overdue_projects_count": overdue_projects_count,
            "projects_by_status": projects_by_status,
            "projects_by_type": projects_by_type
        })
