from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from .models import FollowUp
from .serializers import FollowUpSerializer

class FollowUpViewSet(viewsets.ModelViewSet):
    queryset = FollowUp.objects.all().order_by('scheduled_at')
    serializer_class = FollowUpSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['status', 'follow_up_type', 'related_to_type', 'assigned_to']
    search_fields = ['title', 'description', 'outcome']
    ordering_fields = ['scheduled_at', 'created_at']

    # GET /api/followups/my/
    @action(detail=False, methods=['get'], url_path='my')
    def my_followups(self, request):
        followups = self.filter_queryset(self.get_queryset().filter(assigned_to=request.user))
        return Response(FollowUpSerializer(followups, many=True, context={'request': request}).data)

    # GET /api/followups/today/
    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        followups = self.filter_queryset(self.get_queryset().filter(
            scheduled_at__range=(today_start, today_end)
        ))
        return Response(FollowUpSerializer(followups, many=True, context={'request': request}).data)

    # GET /api/followups/overdue/
    @action(detail=False, methods=['get'], url_path='overdue')
    def overdue(self, request):
        now = timezone.now()
        followups = self.filter_queryset(self.get_queryset().filter(
            ~Q(status='Completed') & ~Q(status='Cancelled') & Q(scheduled_at__lt=now)
        ))
        return Response(FollowUpSerializer(followups, many=True, context={'request': request}).data)

    # GET /api/followups/upcoming/
    @action(detail=False, methods=['get'], url_path='upcoming')
    def upcoming(self, request):
        now = timezone.now()
        next_week = now + timezone.timedelta(days=7)
        followups = self.filter_queryset(self.get_queryset().filter(
            scheduled_at__range=(now, next_week)
        ))
        return Response(FollowUpSerializer(followups, many=True, context={'request': request}).data)

    # PATCH /api/followups/{id}/complete/
    @action(detail=True, methods=['patch'], url_path='complete')
    def complete(self, request, pk=None):
        followup = self.get_object()
        outcome = request.data.get('outcome', '')
        
        followup.status = 'Completed'
        followup.outcome = outcome
        followup.save()
        return Response(FollowUpSerializer(followup, context={'request': request}).data)

    # PATCH /api/followups/{id}/reschedule/
    @action(detail=True, methods=['patch'], url_path='reschedule')
    def reschedule(self, request, pk=None):
        followup = self.get_object()
        new_date = request.data.get('scheduled_at')
        if not new_date:
            return Response({"error": "scheduled_at field is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        followup.scheduled_at = new_date
        followup.status = 'Rescheduled'
        followup.reschedule_count += 1
        followup.save()
        return Response(FollowUpSerializer(followup, context={'request': request}).data)
