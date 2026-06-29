from rest_framework import serializers
from .models import Campaign, ContentCalendarItem
from django.contrib.auth import get_user_model

User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_name', 'email', 'avatar', 'role')

class CampaignSerializer(serializers.ModelSerializer):
    roi = serializers.ReadOnlyField()
    created_by_detail = UserShortSerializer(source='created_by', read_only=True)

    class Meta:
        model = Campaign
        fields = '__all__'
        read_only_fields = ('created_by',)

class ContentCalendarItemSerializer(serializers.ModelSerializer):
    author_detail = UserShortSerializer(source='author', read_only=True)
    reviewer_detail = UserShortSerializer(source='reviewer', read_only=True)

    class Meta:
        model = ContentCalendarItem
        fields = '__all__'
        read_only_fields = ('author',)
