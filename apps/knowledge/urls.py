from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KnowledgeArticleViewSet

router = DefaultRouter()
router.register('articles', KnowledgeArticleViewSet, basename='articles')

urlpatterns = [
    path('', include(router.urls)),
]
