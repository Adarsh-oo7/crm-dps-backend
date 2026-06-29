from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TeamMemberViewSet, AttendanceViewSet, LeaveRequestViewSet, DailyWorkLogViewSet

router = DefaultRouter()
router.register('members', TeamMemberViewSet, basename='members')
router.register('attendance', AttendanceViewSet, basename='attendance')
router.register('leave-requests', LeaveRequestViewSet, basename='leave_requests')
router.register('work-logs', DailyWorkLogViewSet, basename='work_logs')

urlpatterns = [
    path('', include(router.urls)),
]
