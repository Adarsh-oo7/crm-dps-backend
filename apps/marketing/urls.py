from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, ContentCalendarItemViewSet

router = DefaultRouter()
router.register('campaigns', CampaignViewSet, basename='campaigns')
router.register('content', ContentCalendarItemViewSet, basename='content')

urlpatterns = [
    path('', include(router.urls)),
]
