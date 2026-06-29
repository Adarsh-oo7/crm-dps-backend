from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, ProductFeatureViewSet, ProductBugViewSet

router = DefaultRouter()
router.register('products', ProductViewSet, basename='products')
router.register('features', ProductFeatureViewSet, basename='features')
router.register('bugs', ProductBugViewSet, basename='bugs')

urlpatterns = [
    path('', include(router.urls)),
]
