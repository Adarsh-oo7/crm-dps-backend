from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Client, ClientContact, ClientDocument
from .serializers import ClientSerializer, ClientContactSerializer, ClientDocumentSerializer
from apps.projects.serializers import ProjectSerializer # We will create projects serializers next

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by('-created_at')
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['status', 'client_type', 'account_manager', 'support_person']
    search_fields = ['company_name', 'industry', 'city', 'country']
    ordering_fields = ['created_at', 'company_name']

    def perform_destroy(self, instance):
        # Soft delete: update status to Inactive instead of deleting record
        instance.status = 'Inactive'
        instance.save()

    # GET/POST /api/clients/{id}/contacts/
    @action(detail=True, methods=['get', 'post'], url_path='contacts')
    def contacts(self, request, pk=None):
        client = self.get_object()
        if request.method == 'GET':
            contacts = client.contacts.all()
            return Response(ClientContactSerializer(contacts, many=True).data)
            
        elif request.method == 'POST':
            serializer = ClientContactSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(client=client)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # PUT/DELETE /api/clients/{id}/contacts/{cid}/
    @action(detail=True, methods=['put', 'delete'], url_path=r'contacts/(?P<cid>\d+)')
    def contact_detail(self, request, pk=None, cid=None):
        client = self.get_object()
        contact = get_object_or_404(ClientContact, id=cid, client=client)
        
        if request.method == 'PUT':
            serializer = ClientContactSerializer(contact, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        elif request.method == 'DELETE':
            contact.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    # GET/POST /api/clients/{id}/documents/
    @action(detail=True, methods=['get', 'post'], url_path='documents')
    def documents(self, request, pk=None):
        client = self.get_object()
        if request.method == 'GET':
            docs = client.documents.all().order_by('-uploaded_at')
            return Response(ClientDocumentSerializer(docs, many=True, context={'request': request}).data)
            
        elif request.method == 'POST':
            serializer = ClientDocumentSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(client=client, uploaded_by=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # GET /api/clients/{id}/projects/
    @action(detail=True, methods=['get'], url_path='projects')
    def projects(self, request, pk=None):
        client = self.get_object()
        projects = client.projects.all().order_by('-created_at')
        return Response(ProjectSerializer(projects, many=True, context={'request': request}).data)

    # GET /api/clients/{id}/invoices/
    @action(detail=True, methods=['get'], url_path='invoices')
    def invoices(self, request, pk=None):
        client = self.get_object()
        # Invoices will be defined in the finance module later. Let's return empty array if the model doesn't exist yet, or query if it does.
        try:
            invoices = client.invoices.all().order_by('-invoice_date')
            # For now, return serialized invoices if we have finance app initialized
            from apps.finance.serializers import InvoiceSerializer
            return Response(InvoiceSerializer(invoices, many=True, context={'request': request}).data)
        except Exception:
            return Response([])

    # GET /api/clients/{id}/timeline/
    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, pk=None):
        client = self.get_object()
        timeline_data = []
        
        # 1. Gather logs from Lead Activity if company name matches
        from apps.leads.models import LeadActivityTimeline
        lead_logs = LeadActivityTimeline.objects.filter(lead__company_name=client.company_name).order_by('-created_at')[:10]
        for log in lead_logs:
            timeline_data.append({
                "type": "Lead CRM",
                "action": log.activity_type,
                "description": log.description,
                "user": log.user.full_name if log.user else "System",
                "timestamp": log.created_at
            })
            
        # Sort combined timeline
        timeline_data.sort(key=lambda x: x['timestamp'], reverse=True)
        return Response(timeline_data)
