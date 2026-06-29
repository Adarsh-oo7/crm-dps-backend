from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Lead, LeadActivityTimeline
from apps.projects.serializers import ProjectSerializer
from apps.products.serializers import ProductSerializer

User = get_user_model()

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'avatar')

class LeadActivityTimelineSerializer(serializers.ModelSerializer):
    user_detail = UserSimpleSerializer(source='user', read_only=True)
    
    class Meta:
        model = LeadActivityTimeline
        fields = ('id', 'lead', 'user', 'user_detail', 'activity_type', 'description', 'created_at')
        read_only_fields = ('id', 'created_at')

class LeadSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserSimpleSerializer(source='assigned_to', read_only=True)
    created_by_detail = UserSimpleSerializer(source='created_by', read_only=True)
    project_detail = ProjectSerializer(source='project', read_only=True)
    product_detail = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'created_by')

    def create(self, validated_data):
        # Automatically set created_by to current request user
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)
