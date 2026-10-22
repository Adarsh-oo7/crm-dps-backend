from django.urls import path
from .intern_views import interns, intern_reports, intern_report_status

urlpatterns = [
    path('', interns, name='interns'),
    path('reports/', intern_reports, name='intern_reports'),
    path('reports/<int:pk>/', intern_report_status, name='intern_report_status'),
]
