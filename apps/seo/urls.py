from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SEOKeywordViewSet, SEOReportViewSet

router = DefaultRouter()
router.register('keywords', SEOKeywordViewSet, basename='keywords')
router.register('reports', SEOReportViewSet, basename='reports')

urlpatterns = [
    path('', include(router.urls)),
]
