from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomainViewSet, HostingViewSet, SSLCertificateViewSet, expiry_alerts

router = DefaultRouter()
router.register('domains', DomainViewSet, basename='domains')
router.register('hosting', HostingViewSet, basename='hosting')
router.register('ssl', SSLCertificateViewSet, basename='ssl')

urlpatterns = [
    path('expiry-alerts/', expiry_alerts, name='expiry_alerts'),
    path('', include(router.urls)),
]
