from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.projects.models import Project
from apps.clients.models import Client
from .models import Task, TaskChecklistItem, TaskComment, TaskTimeLog, TaskAttachment

User = get_user_model()

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'avatar')

class ProjectSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ('id', 'name')

class ClientSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ('id', 'name', 'company_name')

class TaskChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskChecklistItem
        fields = '__all__'

class TaskCommentSerializer(serializers.ModelSerializer):
    user_detail = UserSimpleSerializer(source='user', read_only=True)

    class Meta:
        model = TaskComment
        fields = '__all__'
        read_only_fields = ('user', 'created_at', 'updated_at')

class TaskTimeLogSerializer(serializers.ModelSerializer):
    user_detail = UserSimpleSerializer(source='user', read_only=True)

    class Meta:
        model = TaskTimeLog
        fields = '__all__'
        read_only_fields = ('user', 'duration_minutes', 'created_at')

class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_detail = UserSimpleSerializer(source='uploaded_by', read_only=True)

    class Meta:
        model = TaskAttachment
        fields = '__all__'
        read_only_fields = ('uploaded_by', 'uploaded_at')

class TaskSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserSimpleSerializer(source='assigned_to', read_only=True)
    assigned_by_detail = UserSimpleSerializer(source='assigned_by', read_only=True)
    created_by_detail = UserSimpleSerializer(source='created_by', read_only=True)
    project_detail = ProjectSimpleSerializer(source='project', read_only=True)
    client_detail = ClientSimpleSerializer(source='client', read_only=True)
    checklist_items = TaskChecklistItemSerializer(many=True, read_only=True)
    comments = TaskCommentSerializer(many=True, read_only=True)
    timelogs = TaskTimeLogSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    logged_hours = serializers.ReadOnlyField()
    active_timer_detail = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'created_by', 'assigned_by')

    def get_active_timer_detail(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            active_log = obj.timelogs.filter(user=request.user, ended_at__isnull=True).first()
            if active_log:
                return TaskTimeLogSerializer(active_log).data
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            validated_data['assigned_by'] = request.user
        return super().create(validated_data)
