from rest_framework import serializers
from .models import Proposal, ProposalLineItem, Invoice, InvoiceLineItem, Payment, Expense, Quotation, QuotationLineItem
from apps.clients.serializers import ClientSerializer
from apps.projects.serializers import ProjectSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_name', 'email', 'avatar', 'role')

# Line Items
class ProposalLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalLineItem
        fields = '__all__'
        read_only_fields = ('total',)

class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = '__all__'
        read_only_fields = ('total',)

class QuotationLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationLineItem
        fields = '__all__'
        read_only_fields = ('total',)

# Parents
class ProposalSerializer(serializers.ModelSerializer):
    line_items = ProposalLineItemSerializer(many=True, required=False)
    client_detail = ClientSerializer(source='client', read_only=True)
    created_by_detail = UserShortSerializer(source='created_by', read_only=True)

    class Meta:
        model = Proposal
        fields = '__all__'
        read_only_fields = ('proposal_number', 'created_by')

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        proposal = Proposal.objects.create(**validated_data)
        for item_data in line_items_data:
            ProposalLineItem.objects.create(proposal=proposal, **item_data)
        return proposal

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)
        instance = super().update(instance, validated_data)
        if line_items_data is not None:
            instance.line_items.all().delete()
            for item_data in line_items_data:
                ProposalLineItem.objects.create(proposal=instance, **item_data)
        return instance

class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, required=False)
    client_detail = ClientSerializer(source='client', read_only=True)
    project_detail = ProjectSerializer(source='project', read_only=True)
    created_by_detail = UserShortSerializer(source='created_by', read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ('invoice_number', 'created_by', 'subtotal', 'tax_amount', 'discount_amount', 'total_amount')

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        invoice = Invoice.objects.create(**validated_data)
        for item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=invoice, **item_data)
        invoice.recalculate_totals()
        return invoice

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)
        instance = super().update(instance, validated_data)
        if line_items_data is not None:
            instance.line_items.all().delete()
            for item_data in line_items_data:
                InvoiceLineItem.objects.create(invoice=instance, **item_data)
            instance.recalculate_totals()
        return instance

class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_detail = UserShortSerializer(source='recorded_by', read_only=True)
    invoice_number = serializers.ReadOnlyField(source='invoice.invoice_number')

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('recorded_by',)

class ExpenseSerializer(serializers.ModelSerializer):
    paid_by_detail = UserShortSerializer(source='paid_by', read_only=True)
    approved_by_detail = UserShortSerializer(source='approved_by', read_only=True)
    client_detail = ClientSerializer(source='client', read_only=True)
    project_detail = ProjectSerializer(source='project', read_only=True)

    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ('paid_by', 'approved_by', 'approved_at')

class QuotationSerializer(serializers.ModelSerializer):
    line_items = QuotationLineItemSerializer(many=True, required=False)
    client_detail = ClientSerializer(source='client', read_only=True)
    created_by_detail = UserShortSerializer(source='created_by', read_only=True)

    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ('quotation_number', 'created_by')

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        quotation = Quotation.objects.create(**validated_data)
        for item_data in line_items_data:
            QuotationLineItem.objects.create(quotation=quotation, **item_data)
        return quotation

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)
        instance = super().update(instance, validated_data)
        if line_items_data is not None:
            instance.line_items.all().delete()
            for item_data in line_items_data:
                QuotationLineItem.objects.create(quotation=instance, **item_data)
        return instance
