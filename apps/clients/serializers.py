from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Client, ClientContact, ClientDocument

User = get_user_model()

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'avatar')

class ClientContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientContact
        fields = '__all__'
        read_only_fields = ('client',)

class ClientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_detail = UserSimpleSerializer(source='uploaded_by', read_only=True)

    class Meta:
        model = ClientDocument
        fields = '__all__'
        read_only_fields = ('client', 'uploaded_by', 'uploaded_at')

class ClientSerializer(serializers.ModelSerializer):
    account_manager_detail = UserSimpleSerializer(source='account_manager', read_only=True)
    support_person_detail = UserSimpleSerializer(source='support_person', read_only=True)
    created_by_detail = UserSimpleSerializer(source='created_by', read_only=True)
    contacts = ClientContactSerializer(many=True, read_only=True)
    documents = ClientDocumentSerializer(many=True, read_only=True)
    total_revenue = serializers.ReadOnlyField(source='total_revenue_generated')

    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'created_by')

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)
