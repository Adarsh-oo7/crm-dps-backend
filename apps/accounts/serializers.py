from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    modules = serializers.SerializerMethodField()
    desk = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'full_name', 'phone', 'role',
            'department', 'avatar', 'is_active', 'is_online',
            'last_seen', 'date_joined', 'whatsapp_number',
            'notification_preferences', 'password', 'custom_permissions',
            'modules', 'desk',
        )
        read_only_fields = ('id', 'date_joined', 'last_seen')

    def get_modules(self, obj):
        from .access import modules_for
        return sorted(modules_for(obj))

    def get_desk(self, obj):
        from .access import desk_for
        return desk_for(obj)

    def create(self, validated_data):
        password = (validated_data.pop('password', None) or '').strip() or 'DpsUser@123'
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password and str(password).strip():
            instance.set_password(str(password).strip())
        instance.save()
        return instance

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        raw_email = (attrs.get(self.username_field) or '').strip()
        candidates = [raw_email]
        for base in list(candidates):
            if 'official' in base.lower():
                candidates.append(base.lower().replace('official', 'offical'))
            if 'offical' in base.lower():
                candidates.append(base.lower().replace('offical', 'official'))
        for base in list(candidates):
            if 'hrishi' in base.lower():
                candidates.append(base.lower().replace('hrishi', 'hirshi'))
            if 'hirshi' in base.lower():
                candidates.append(base.lower().replace('hirshi', 'hrishi'))

        for candidate in candidates:
            user = User.objects.filter(email__iexact=candidate).first()
            if user:
                attrs[self.username_field] = user.email
                break

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

