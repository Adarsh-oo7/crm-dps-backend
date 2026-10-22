from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProposalViewSet, QuotationViewSet, InvoiceViewSet,
    PaymentViewSet, ExpenseViewSet, finance_summary,
    revenue_chart, outstanding_invoices, project_money,
    rentals, collect, update_gear,
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
    path('projects/', project_money, name='project_money'),
    path('rentals/', rentals, name='rentals'),
    path('collect/', collect, name='collect_money'),
    path('gear/<int:pk>/', update_gear, name='update_gear'),
    path('', include(router.urls)),
]
