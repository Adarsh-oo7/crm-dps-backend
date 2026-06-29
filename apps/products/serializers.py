from rest_framework import serializers
from .models import Product, ProductFeature, ProductBug
from django.contrib.auth import get_user_model

User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_name', 'email', 'avatar', 'role')

class ProductSerializer(serializers.ModelSerializer):
    project_manager_detail = UserShortSerializer(source='project_manager', read_only=True)
    team_members_detail = UserShortSerializer(source='team_members', many=True, read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

class ProductFeatureSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserShortSerializer(source='assigned_to', read_only=True)

    class Meta:
        model = ProductFeature
        fields = '__all__'

class ProductBugSerializer(serializers.ModelSerializer):
    reported_by_detail = UserShortSerializer(source='reported_by', read_only=True)
    assigned_to_detail = UserShortSerializer(source='assigned_to', read_only=True)

    class Meta:
        model = ProductBug
        fields = '__all__'
        read_only_fields = ('reported_by',)
