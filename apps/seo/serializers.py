from rest_framework import serializers
from .models import SEOKeyword, SEORankLog, SEOReport
from apps.clients.serializers import ClientSerializer
from apps.projects.serializers import ProjectSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_name', 'email', 'avatar', 'role')

class SEOKeywordSerializer(serializers.ModelSerializer):
    client_detail = ClientSerializer(source='client', read_only=True)
    project_detail = ProjectSerializer(source='project', read_only=True)
    assigned_to_detail = UserShortSerializer(source='assigned_to', read_only=True)

    class Meta:
        model = SEOKeyword
        fields = '__all__'

class SEORankLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEORankLog
        fields = '__all__'
        read_only_fields = ('keyword',)

class SEOReportSerializer(serializers.ModelSerializer):
    client_detail = ClientSerializer(source='client', read_only=True)
    created_by_detail = UserShortSerializer(source='created_by', read_only=True)

    class Meta:
        model = SEOReport
        fields = '__all__'
        read_only_fields = ('created_by',)
