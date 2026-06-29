from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'full_name', 'phone', 'role', 
            'department', 'avatar', 'is_active', 'is_online', 
            'last_seen', 'date_joined', 'whatsapp_number', 
            'notification_preferences', 'password', 'custom_permissions'
        )
        read_only_fields = ('id', 'date_joined', 'last_seen')

    def create(self, validated_data):
        password = validated_data.pop('password', 'DpsUser@123')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add custom claims
        data['user'] = UserSerializer(self.user).data
        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


from .models import Attendance, LeaveRequest, DailyWorkLog

class AttendanceSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ('user', 'duration_hours')

class LeaveRequestSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source='user', read_only=True)
    approved_by_detail = UserSerializer(source='approved_by', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ('user', 'days_requested', 'approved_by', 'approved_at')

class DailyWorkLogSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source='user', read_only=True)

    class Meta:
        model = DailyWorkLog
        fields = '__all__'
        read_only_fields = ('user',)

