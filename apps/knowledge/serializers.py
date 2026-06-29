from rest_framework import serializers
from .models import KnowledgeArticle
from django.contrib.auth import get_user_model

User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_name', 'email', 'avatar', 'role')

class KnowledgeArticleSerializer(serializers.ModelSerializer):
    author_detail = UserShortSerializer(source='author', read_only=True)
    last_updated_by_detail = UserShortSerializer(source='last_updated_by', read_only=True)

    class Meta:
        model = KnowledgeArticle
        fields = '__all__'
        read_only_fields = ('author', 'last_updated_by', 'view_count')
