from rest_framework import serializers
from .models import Domain, Hosting, SSLCertificate
from apps.clients.serializers import ClientSerializer
from apps.projects.serializers import ProjectSerializer

class DomainSerializer(serializers.ModelSerializer):
    client_detail = ClientSerializer(source='client', read_only=True)
    project_detail = ProjectSerializer(source='project', read_only=True)

    class Meta:
        model = Domain
        fields = '__all__'
        read_only_fields = ('created_by',)

class HostingSerializer(serializers.ModelSerializer):
    client_detail = ClientSerializer(source='client', read_only=True)

    class Meta:
        model = Hosting
        fields = '__all__'
        read_only_fields = ('created_by',)

class SSLCertificateSerializer(serializers.ModelSerializer):
    domain_detail = DomainSerializer(source='domain', read_only=True)

    class Meta:
        model = SSLCertificate
        fields = '__all__'
