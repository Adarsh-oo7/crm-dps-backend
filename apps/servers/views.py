from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import datetime

from .models import Domain, Hosting, SSLCertificate
from .serializers import DomainSerializer, HostingSerializer, SSLCertificateSerializer

class DomainViewSet(viewsets.ModelViewSet):
    queryset = Domain.objects.all().order_by('expiry_date')
    serializer_class = DomainSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'registrar', 'client']
    search_fields = ['domain_name', 'notes']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class HostingViewSet(viewsets.ModelViewSet):
    queryset = Hosting.objects.all().order_by('renewal_date')
    serializer_class = HostingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'provider', 'server_type', 'client']
    search_fields = ['server_name', 'ip_address', 'notes']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SSLCertificateViewSet(viewsets.ModelViewSet):
    queryset = SSLCertificate.objects.all().order_by('expiry_date')
    serializer_class = SSLCertificateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'issuer']


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiry_alerts(request):
    today = timezone.localdate()
    domain_expiry_limit = today + datetime.timedelta(days=30)
    ssl_expiry_limit = today + datetime.timedelta(days=14)
    hosting_renewal_limit = today + datetime.timedelta(days=7)

    expiring_domains = Domain.objects.filter(expiry_date__range=(today, domain_expiry_limit))
    expiring_ssl = SSLCertificate.objects.filter(expiry_date__range=(today, ssl_expiry_limit))
    expiring_hosting = Hosting.objects.filter(renewal_date__range=(today, hosting_renewal_limit))

    return Response({
        "domains": DomainSerializer(expiring_domains, many=True, context={'request': request}).data,
        "ssl": SSLCertificateSerializer(expiring_ssl, many=True, context={'request': request}).data,
        "hosting": HostingSerializer(expiring_hosting, many=True, context={'request': request}).data,
    })
