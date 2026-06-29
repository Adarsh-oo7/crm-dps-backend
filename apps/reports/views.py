from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q, Sum, Avg, Count
from django.utils import timezone
import datetime

# Models imports
from apps.leads.models import Lead
from apps.clients.models import Client
from apps.projects.models import Project
from apps.tasks.models import Task

class GlobalSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({
                "leads": [], "clients": [], "projects": [],
                "tasks": [], "invoices": [], "articles": []
            })

        results = {}

        # 1. Leads
        try:
            from apps.leads.serializers import LeadSerializer
            leads = Lead.objects.filter(
                Q(company_name__icontains=query) |
                Q(contact_person__icontains=query) |
                Q(email__icontains=query)
            )[:5]
            results['leads'] = LeadSerializer(leads, many=True, context={'request': request}).data
        except Exception:
            results['leads'] = []

        # 2. Clients
        try:
            from apps.clients.serializers import ClientSerializer
            clients = Client.objects.filter(
                Q(company_name__icontains=query) |
                Q(industry__icontains=query)
            )[:5]
            results['clients'] = ClientSerializer(clients, many=True, context={'request': request}).data
        except Exception:
            results['clients'] = []

        # 3. Projects
        try:
            from apps.projects.serializers import ProjectSerializer
            projects = Project.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )[:5]
            results['projects'] = ProjectSerializer(projects, many=True, context={'request': request}).data
        except Exception:
            results['projects'] = []

        # 4. Tasks
        try:
            from apps.tasks.serializers import TaskSerializer
            tasks = Task.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )[:5]
            results['tasks'] = TaskSerializer(tasks, many=True, context={'request': request}).data
        except Exception:
            results['tasks'] = []

        # 5. Invoices
        try:
            from apps.finance.models import Invoice
            from apps.finance.serializers import InvoiceSerializer
            invoices = Invoice.objects.filter(
                Q(invoice_number__icontains=query) |
                Q(notes__icontains=query)
            )[:5]
            results['invoices'] = InvoiceSerializer(invoices, many=True, context={'request': request}).data
        except Exception:
            results['invoices'] = []

        # 6. Articles
        try:
            from apps.knowledge.models import KnowledgeArticle
            from apps.knowledge.serializers import KnowledgeArticleSerializer
            articles = KnowledgeArticle.objects.filter(
                Q(title__icontains=query) |
                Q(content__icontains=query)
            )[:5]
            results['articles'] = KnowledgeArticleSerializer(articles, many=True, context={'request': request}).data
        except Exception:
            results['articles'] = []

        return Response(results)


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        
        # Core stats counts
        total_leads = Lead.objects.count()
        hot_leads = Lead.objects.filter(priority='Hot').count()
        active_projects = Project.objects.filter(status__in=['Planning', 'UI Design', 'Development', 'Testing']).count()
        my_tasks_today = Task.objects.filter(assigned_to=request.user, due_date__date=today).count()
        
        # Finance aggregates
        total_revenue = 0.0
        total_expenses = 0.0
        try:
            from apps.finance.models import Invoice, Expense
            total_revenue = float(Invoice.objects.filter(
                invoice_date__gte=start_of_month,
                status='Paid'
            ).aggregate(total=Sum('total_amount'))['total'] or 0.0)

            total_expenses = float(Expense.objects.filter(
                expense_date__gte=start_of_month,
                status='Approved'
            ).aggregate(total=Sum('amount'))['total'] or 0.0)
        except Exception:
            pass

        # Follow-ups due today
        today_followups_count = 0
        try:
            from apps.followups.models import FollowUp
            today_followups_count = FollowUp.objects.filter(
                assigned_to=request.user,
                scheduled_at__date=today,
                status='Pending'
            ).count()
        except Exception:
            pass

        return Response({
            "leads_count": total_leads,
            "hot_leads_count": hot_leads,
            "active_projects_count": active_projects,
            "my_tasks_today_count": my_tasks_today,
            "revenue_this_month": total_revenue,
            "expenses_this_month": total_expenses,
            "profit_this_month": total_revenue - total_expenses,
            "today_followups_count": today_followups_count
        })


class ReportsSalesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        leads = Lead.objects.all()
        total_leads = leads.count()
        leads_won = leads.filter(status='Won').count()
        conversion_rate = (leads_won / total_leads * 100) if total_leads > 0 else 0.0
        
        leads_by_status = leads.values('status').annotate(count=Count('id'))
        leads_by_source = leads.values('lead_source').annotate(count=Count('id'))
        
        return Response({
            "total_leads": total_leads,
            "leads_won": leads_won,
            "conversion_rate": conversion_rate,
            "leads_by_status": list(leads_by_status),
            "leads_by_source": list(leads_by_source)
        })


class ReportsProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = Project.objects.all()
        projects_by_status = projects.values('status').annotate(count=Count('id'))
        projects_by_priority = projects.values('priority').annotate(count=Count('id'))
        
        # Overdue milestones
        overdue_milestones = 0
        try:
            from apps.projects.models import Milestone
            overdue_milestones = Milestone.objects.filter(
                due_date__lt=timezone.now(),
                status__in=['Pending', 'In Progress']
            ).count()
        except Exception:
            pass

        return Response({
            "total_projects": projects.count(),
            "projects_by_status": list(projects_by_status),
            "projects_by_priority": list(projects_by_priority),
            "overdue_milestones_count": overdue_milestones
        })
