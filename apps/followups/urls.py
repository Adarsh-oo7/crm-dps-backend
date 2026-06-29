from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FollowUpViewSet

router = DefaultRouter()
router.register(r'', FollowUpViewSet, basename='followups')

urlpatterns = [
    path('', include(router.urls)),
]
