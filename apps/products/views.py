from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, ProductFeature, ProductBug
from .serializers import ProductSerializer, ProductFeatureSerializer, ProductBugSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['product_type', 'status', 'pricing_model']
    search_fields = ['name', 'tagline', 'description']


class ProductFeatureViewSet(viewsets.ModelViewSet):
    queryset = ProductFeature.objects.all().order_by('status', '-priority')
    serializer_class = ProductFeatureSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['product', 'status', 'priority', 'assigned_to']
    search_fields = ['title', 'description']


class ProductBugViewSet(viewsets.ModelViewSet):
    queryset = ProductBug.objects.all().order_by('-severity', '-created_at')
    serializer_class = ProductBugSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['product', 'status', 'severity', 'assigned_to', 'environment']
    search_fields = ['title', 'description']

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)
