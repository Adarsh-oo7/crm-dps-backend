from django.urls import path
from .views import (
    GlobalSearchView, DashboardSummaryView, 
    ReportsSalesView, ReportsProjectsView
)

urlpatterns = [
    path('search/', GlobalSearchView.as_view(), name='global_search'),
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard_summary'),
    path('reports/sales/', ReportsSalesView.as_view(), name='reports_sales'),
    path('reports/projects/', ReportsProjectsView.as_view(), name='reports_projects'),
]
