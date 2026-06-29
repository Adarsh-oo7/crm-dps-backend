from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProposalViewSet, QuotationViewSet, InvoiceViewSet,
    PaymentViewSet, ExpenseViewSet, finance_summary,
    revenue_chart, outstanding_invoices
)

router = DefaultRouter()
router.register('proposals', ProposalViewSet, basename='proposals')
router.register('quotations', QuotationViewSet, basename='quotations')
router.register('invoices', InvoiceViewSet, basename='invoices')
router.register('payments', PaymentViewSet, basename='payments')
router.register('expenses', ExpenseViewSet, basename='expenses')

urlpatterns = [
    path('summary/', finance_summary, name='finance_summary'),
    path('revenue-chart/', revenue_chart, name='revenue_chart'),
    path('outstanding/', outstanding_invoices, name='outstanding_invoices'),
    path('', include(router.urls)),
]
