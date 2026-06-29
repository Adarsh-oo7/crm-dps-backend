from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models

from .models import KnowledgeArticle
from .serializers import KnowledgeArticleSerializer

class KnowledgeArticleViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeArticleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_confidential']
    search_fields = ['title', 'content']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['superadmin', 'admin']:
            return KnowledgeArticle.objects.all().order_by('-updated_at')
        
        return KnowledgeArticle.objects.filter(
            models.Q(visibility='All') |
            models.Q(visibility='Specific Roles', allowed_roles__contains=user.role)
        ).order_by('-updated_at')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, last_updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='categories')
    def categories(self, request):
        qs = self.get_queryset()
        categories_count = qs.values('category').annotate(count=models.Count('id'))
        return Response(categories_count)
