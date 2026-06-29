from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, CustomTokenObtainPairSerializer, ChangePasswordSerializer

User = get_user_model()

import random
import logging
from django.conf import settings
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserOTP

log = logging.getLogger(__name__)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response({"detail": "No active account found with the given credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        
        user = serializer.user
        if user.role == 'superadmin':
            # Generate 6-digit OTP
            otp_val = str(random.randint(100000, 999999))
            UserOTP.objects.filter(user=user, purpose='login').update(is_verified=True) # invalidate old ones
            UserOTP.objects.create(user=user, otp=otp_val, purpose='login')
            
            # Send Email
            subject = "🔒 Your DPS OS Verification Code"
            body = (
                f"Hi {user.full_name or 'Superadmin'},\n\n"
                f"Please use the following 6-digit verification code to complete your login:\n\n"
                f"   ⚡  {otp_val}  ⚡\n\n"
                f"This code will expire in 10 minutes.\n\n"
                f"— DPS OS Security Team"
            )
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            except Exception as e:
                log.error(f"Failed to send OTP email: {e}")
                return Response({"detail": f"Failed to send verification email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({"otp_required": True, "email": user.email}, status=status.HTTP_200_OK)
            
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        otp_val = request.data.get('otp')
        
        if not email or not otp_val:
            return Response({"detail": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
            
        # Check latest OTP
        latest_otp = UserOTP.objects.filter(user=user, purpose='login').order_by('-created_at').first()
        
        if not latest_otp or latest_otp.otp != otp_val or not latest_otp.is_valid():
            return Response({"otp": ["Invalid or expired verification code."]}, status=status.HTTP_400_BAD_REQUEST)
            
        latest_otp.is_verified = True
        latest_otp.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }
        return Response(data, status=status.HTTP_200_OK)

class RequestPasswordOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        otp_val = str(random.randint(100000, 999999))
        UserOTP.objects.filter(user=user, purpose='password_change').update(is_verified=True) # invalidate old
        UserOTP.objects.create(user=user, otp=otp_val, purpose='password_change')
        
        subject = "🔑 Your DPS OS Password Reset Verification Code"
        body = (
            f"Hi {user.full_name or 'there'},\n\n"
            f"Please use the following 6-digit verification code to reset/change your profile password:\n\n"
            f"   ⚡  {otp_val}  ⚡\n\n"
            f"This code will expire in 10 minutes.\n\n"
            f"— DPS OS Security Team"
        )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        except Exception as e:
            return Response({"detail": f"Failed to send email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response({"detail": "Verification code has been sent to your email."}, status=status.HTTP_200_OK)

class ChangePasswordOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        otp_val = request.data.get('otp')
        new_password = request.data.get('new_password')
        
        if not otp_val or not new_password:
            return Response({"detail": "OTP and new password are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        latest_otp = UserOTP.objects.filter(user=user, purpose='password_change').order_by('-created_at').first()
        
        if not latest_otp or latest_otp.otp != otp_val or not latest_otp.is_valid():
            return Response({"otp": ["Invalid or expired verification code."]}, status=status.HTTP_400_BAD_REQUEST)
            
        latest_otp.is_verified = True
        latest_otp.save()
        
        user.set_password(new_password)
        user.save()
        
        return Response({"detail": "Password has been successfully updated."}, status=status.HTTP_200_OK)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


from rest_framework import viewsets
from rest_framework.decorators import action
from django.utils import timezone
from django.db import models
from .models import Attendance, LeaveRequest, DailyWorkLog
from .serializers import AttendanceSerializer, LeaveRequestSerializer, DailyWorkLogSerializer
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer
from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer

class TeamMemberViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('full_name', 'email')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if request.user.role != 'superadmin':
            return Response({"detail": "Only superadmin can add new team members."}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        password = request.data.get('password', 'DpsUser@123')
        user = serializer.instance
        
        subject = "🎉 Welcome to DPS OS — Account Created"
        body = (
            f"Hi {user.full_name or 'Team Member'},\n\n"
            f"Your account has been created on DPS OS by the administrator.\n\n"
            f"Here are your login credentials:\n"
            f"  •  Email: {user.email}\n"
            f"  •  Password: {password}\n\n"
            f"Log in here: https://crm.digitalproductsolutions.in/login\n\n"
            f"— DPS OS Admin Team"
        )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        except Exception as e:
            log.error(f"Failed to send welcome email: {e}")
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        member = self.get_object()
        if request.user.role not in ['superadmin', 'admin'] and request.user.id != member.id:
            return Response({"detail": "You do not have permission to edit this profile."}, status=status.HTTP_403_FORBIDDEN)
        
        password = request.data.get('password')
        response = super().update(request, *args, **kwargs)
        
        if password and request.user.role in ['superadmin', 'admin']:
            subject = "🔒 Your DPS OS Password has been reset"
            body = (
                f"Hi {member.full_name or member.email},\n\n"
                f"Your account password has been updated by the administrator.\n\n"
                f"Your new password is: {password}\n\n"
                f"Please log in and update your password: https://crm.digitalproductsolutions.in/login\n\n"
                f"— DPS OS Admin Team"
            )
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [member.email], fail_silently=False)
            except Exception as e:
                log.error(f"Failed to send password reset email: {e}")
                
        return response

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'superadmin':
            return Response({"detail": "Only superadmin can remove team members."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        member = self.get_object()
        tasks = Task.objects.filter(assigned_to=member)
        return Response(TaskSerializer(tasks, many=True, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def projects(self, request, pk=None):
        member = self.get_object()
        projects = Project.objects.filter(models.Q(project_manager=member) | models.Q(team_members=member)).distinct()
        return Response(ProjectSerializer(projects, many=True, context={'request': request}).data)

class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in ['superadmin', 'admin', 'manager']:
            return Attendance.objects.all().order_by('-date', '-check_in')
        return Attendance.objects.filter(user=self.request.user).order_by('-date', '-check_in')

    @action(detail=False, methods=['post'], url_path='check-in')
    def check_in(self, request):
        today = timezone.localdate()
        attendance, created = Attendance.objects.get_or_create(
            user=request.user,
            date=today,
            defaults={
                'check_in': timezone.localtime().time(),
                'status': 'Present'
            }
        )
        if not created:
            return Response({"detail": "Already checked in today."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AttendanceSerializer(attendance).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='check-out')
    def check_out(self, request):
        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(user=request.user, date=today)
        except Attendance.DoesNotExist:
            return Response({"detail": "No check-in found for today."}, status=status.HTTP_400_BAD_REQUEST)
        
        attendance.check_out = timezone.localtime().time()
        attendance.save()
        return Response(AttendanceSerializer(attendance).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='my')
    def my_attendance(self, request):
        queryset = Attendance.objects.filter(user=request.user).order_by('-date')
        return Response(AttendanceSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'], url_path='today')
    def today_attendance(self, request):
        if request.user.role not in ['superadmin', 'admin', 'manager']:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        today = timezone.localdate()
        queryset = Attendance.objects.filter(date=today)
        return Response(AttendanceSerializer(queryset, many=True).data)

class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in ['superadmin', 'admin', 'manager']:
            return LeaveRequest.objects.all().order_by('-created_at')
        return LeaveRequest.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='my')
    def my_leaves(self, request):
        queryset = LeaveRequest.objects.filter(user=request.user).order_by('-created_at')
        return Response(LeaveRequestSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'], url_path='pending')
    def pending_leaves(self, request):
        if request.user.role not in ['superadmin', 'admin', 'manager']:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        queryset = LeaveRequest.objects.filter(status='Pending').order_by('-created_at')
        return Response(LeaveRequestSerializer(queryset, many=True).data)

    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, pk=None):
        if request.user.role not in ['superadmin', 'admin', 'manager']:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        leave = self.get_object()
        leave.status = 'Approved'
        leave.approved_by = request.user
        leave.approved_at = timezone.now()
        leave.notes = request.data.get('notes', leave.notes)
        leave.save()
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=True, methods=['patch'], url_path='reject')
    def reject(self, request, pk=None):
        if request.user.role not in ['superadmin', 'admin', 'manager']:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        leave = self.get_object()
        leave.status = 'Rejected'
        leave.approved_by = request.user
        leave.approved_at = timezone.now()
        leave.notes = request.data.get('notes', leave.notes)
        leave.save()
        return Response(LeaveRequestSerializer(leave).data)

class DailyWorkLogViewSet(viewsets.ModelViewSet):
    serializer_class = DailyWorkLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in ['superadmin', 'admin', 'manager']:
            return DailyWorkLog.objects.all().order_by('-date', '-created_at')
        return DailyWorkLog.objects.filter(user=self.request.user).order_by('-date', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='my')
    def my_logs(self, request):
        queryset = DailyWorkLog.objects.filter(user=request.user).order_by('-created_at')
        return Response(DailyWorkLogSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'], url_path='all')
    def all_logs(self, request):
        if request.user.role not in ['superadmin', 'admin', 'manager']:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        queryset = DailyWorkLog.objects.all().order_by('-created_at')
        return Response(DailyWorkLogSerializer(queryset, many=True).data)

