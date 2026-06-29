from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Campaign, ContentCalendarItem
from .serializers import CampaignSerializer, ContentCalendarItemSerializer

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('-created_at')
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['campaign_type', 'status', 'platform']
    search_fields = ['name', 'notes']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ContentCalendarItemViewSet(viewsets.ModelViewSet):
    queryset = ContentCalendarItem.objects.all().order_by('-scheduled_date', '-created_at')
    serializer_class = ContentCalendarItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['content_type', 'status', 'platform', 'author']
    search_fields = ['title', 'notes']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar_view(self, request):
        # Return only items scheduled for this month or general range for rendering
        queryset = self.filter_queryset(self.get_queryset())
        serializer = ContentCalendarItemSerializer(queryset, many=True)
        return Response(serializer.data)
