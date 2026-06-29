from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
import datetime

from .models import Proposal, Invoice, Payment, Expense, Quotation
from .serializers import (
    ProposalSerializer, InvoiceSerializer, PaymentSerializer,
    ExpenseSerializer, QuotationSerializer
)
from .pdf_utils import (
    generate_pdf_for_invoice, generate_pdf_for_proposal, generate_pdf_for_quotation
)

class ProposalViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.all().order_by('-created_at')
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'client']
    search_fields = ['project_name', 'proposal_number']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['patch'], url_path='send')
    def send_proposal(self, request, pk=None):
        proposal = self.get_object()
        proposal.status = 'Sent'
        proposal.sent_at = timezone.now()
        proposal.save()
        generate_pdf_for_proposal(proposal)
        return Response(ProposalSerializer(proposal, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        proposal = self.get_object()
        pdf_url = generate_pdf_for_proposal(proposal)
        return Response({"pdf_url": pdf_url})


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all().order_by('-created_at')
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'client', 'lead']
    search_fields = ['quotation_number']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        quotation = self.get_object()
        pdf_url = generate_pdf_for_quotation(quotation)
        return Response({"pdf_url": pdf_url})


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-created_at')
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'client', 'project']
    search_fields = ['invoice_number']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['patch'], url_path='send')
    def send_invoice(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = 'Sent'
        invoice.sent_at = timezone.now()
        invoice.save()
        generate_pdf_for_invoice(invoice)
        return Response(InvoiceSerializer(invoice, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        pdf_url = generate_pdf_for_invoice(invoice)
        return Response({"pdf_url": pdf_url})

    # payments action
    @action(detail=True, methods=['get', 'post'], url_path='payments')
    def payments(self, request, pk=None):
        invoice = self.get_object()
        if request.method == 'GET':
            payments = invoice.payments.all().order_by('-created_at')
            return Response(PaymentSerializer(payments, many=True).data)
        elif request.method == 'POST':
            serializer = PaymentSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(invoice=invoice, recorded_by=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.all().order_by('-created_at')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by('-created_at')
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'category', 'client', 'project']
    search_fields = ['description']

    def perform_create(self, serializer):
        serializer.save(paid_by=self.request.user)

    @action(detail=True, methods=['patch'], url_path='approve')
    def approve(self, request, pk=None):
        if request.user.role not in ['superadmin', 'admin', 'finance']:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        expense = self.get_object()
        expense.status = 'Approved'
        expense.approved_by = request.user
        expense.save()
        return Response(ExpenseSerializer(expense).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def finance_summary(request):
    today = timezone.localdate()
    start_of_month = today.replace(day=1)
    
    # 1. Total Invoiced this month
    total_invoiced = Invoice.objects.filter(
        invoice_date__gte=start_of_month,
        invoice_date__lte=today
    ).aggregate(total=Sum('total_amount'))['total'] or 0.0

    # 2. Total Collected this month (from Payments)
    total_collected = Payment.objects.filter(
        payment_date__gte=datetime.datetime.combine(start_of_month, datetime.time.min),
        payment_date__lte=timezone.now()
    ).aggregate(total=Sum('amount'))['total'] or 0.0

    # 3. Outstanding Payments
    outstanding = Invoice.objects.filter(
        ~Q(status='Paid') & ~Q(status='Cancelled')
    ).aggregate(total=Sum('total_amount'))['total'] or 0.0
    
    # Subtract paid parts from outstanding
    total_paid_on_outstanding = Payment.objects.filter(
        invoice__status__in=['Sent', 'Partially Paid', 'Overdue']
    ).aggregate(total=Sum('amount'))['total'] or 0.0
    
    outstanding_final = max(0.0, float(outstanding) - float(total_paid_on_outstanding))

    # 4. Expenses this month
    total_expenses = Expense.objects.filter(
        expense_date__gte=start_of_month,
        expense_date__lte=today,
        status='Approved'
    ).aggregate(total=Sum('amount'))['total'] or 0.0

    # 5. Profit this month
    profit = float(total_collected) - float(total_expenses)

    return Response({
        "total_invoiced_this_month": total_invoiced,
        "total_collected_this_month": total_collected,
        "outstanding_payments": outstanding_final,
        "expenses_this_month": total_expenses,
        "profit_this_month": profit
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_chart(request):
    # Returns last 6 months P&L data
    today = timezone.localdate()
    months = []
    
    # Populate last 6 months
    for i in range(5, -1, -1):
        dt = today - datetime.timedelta(days=i*30)
        months.append((dt.year, dt.month, dt.strftime("%b %Y")))
        
    chart_data = []
    for year, month, label in months:
        invoices_val = Invoice.objects.filter(
            invoice_date__year=year,
            invoice_date__month=month,
            status__in=['Sent', 'Partially Paid', 'Paid', 'Overdue']
        ).aggregate(total=Sum('total_amount'))['total'] or 0.0

        expenses_val = Expense.objects.filter(
            expense_date__year=year,
            expense_date__month=month,
            status='Approved'
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        chart_data.append({
            "month": label,
            "revenue": invoices_val,
            "expenses": expenses_val,
            "profit": float(invoices_val) - float(expenses_val)
        })

    return Response(chart_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def outstanding_invoices(request):
    invoices = Invoice.objects.filter(
        status__in=['Sent', 'Partially Paid', 'Overdue']
    ).order_by('due_date')
    return Response(InvoiceSerializer(invoices, many=True).data)
