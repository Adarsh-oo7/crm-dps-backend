from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Project, Milestone
from apps.clients.serializers import ClientSerializer

User = get_user_model()

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'avatar')

class MilestoneSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserSimpleSerializer(source='assigned_to', read_only=True)

    class Meta:
        model = Milestone
        fields = '__all__'

class ProjectSerializer(serializers.ModelSerializer):
    client_detail = ClientSerializer(source='client', read_only=True)
    project_manager_detail = UserSimpleSerializer(source='project_manager', read_only=True)
    team_members_detail = UserSimpleSerializer(source='team_members', many=True, read_only=True)
    created_by_detail = UserSimpleSerializer(source='created_by', read_only=True)
    milestones = MilestoneSerializer(many=True, read_only=True)
    logged_hours = serializers.ReadOnlyField(source='hours_logged')

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'created_by')

    def create(self, validated_data):
        request = self.context.get('request')
        # Handle Many-To-Many team_members inside views/serializers
        team_members = validated_data.pop('team_members', [])
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        
        project = Project.objects.create(**validated_data)
        if team_members:
            project.team_members.set(team_members)
        return project
