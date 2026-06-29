from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Count
from .models import SEOKeyword, SEORankLog, SEOReport
from .serializers import SEOKeywordSerializer, SEORankLogSerializer, SEOReportSerializer

class SEOKeywordViewSet(viewsets.ModelViewSet):
    queryset = SEOKeyword.objects.all().order_by('current_position')
    serializer_class = SEOKeywordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'client', 'project', 'assigned_to']
    search_fields = ['keyword', 'target_url']

    @action(detail=True, methods=['get', 'post'], url_path='rank-history')
    def rank_history(self, request, pk=None):
        keyword = self.get_object()
        if request.method == 'GET':
            logs = keyword.rank_logs.all().order_by('-check_date')
            return Response(SEORankLogSerializer(logs, many=True).data)
        elif request.method == 'POST':
            serializer = SEORankLogSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(keyword=keyword)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='stats')
    def seo_stats(self, request):
        keywords = self.filter_queryset(self.get_queryset())
        total_keywords = keywords.count()
        avg_pos = keywords.filter(current_position__gt=0).aggregate(Avg('current_position'))['current_position__avg'] or 0.0
        top_3 = keywords.filter(current_position__range=(1, 3)).count()
        top_10 = keywords.filter(current_position__range=(1, 10)).count()

        return Response({
            "total_keywords": total_keywords,
            "average_position": avg_pos,
            "top_3_count": top_3,
            "top_10_count": top_10
        })


class SEOReportViewSet(viewsets.ModelViewSet):
    queryset = SEOReport.objects.all().order_by('-report_date')
    serializer_class = SEOReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['client']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
