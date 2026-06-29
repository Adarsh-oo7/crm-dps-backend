from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from .models import Lead, LeadActivityTimeline
from .serializers import LeadSerializer, LeadActivityTimelineSerializer
from apps.clients.models import Client, ClientContact # We'll need these for convert action

class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all().order_by('-created_at')
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['status', 'priority', 'assigned_to', 'industry', 'lead_source']
    search_fields = ['company_name', 'contact_person', 'email', 'phone']
    ordering_fields = ['created_at', 'lead_score', 'estimated_value', 'next_followup_date']

    def get_permissions(self):
        # Only admin/superadmin can delete leads
        if self.action == 'destroy':
            return [IsAuthenticated()] # Can enforce custom admin checking here if required, or keep IsAuthenticated for dev and customize later
        return super().get_permissions()

    # GET /api/leads/pipeline/
    @action(detail=False, methods=['get'], url_path='pipeline')
    def pipeline(self, request):
        leads = self.filter_queryset(self.get_queryset())
        stages = [choice[0] for choice in Lead.STATUS_CHOICES]
        
        pipeline_data = {}
        for stage in stages:
            stage_leads = leads.filter(status=stage)
            pipeline_data[stage] = LeadSerializer(stage_leads, many=True, context={'request': request}).data
            
        return Response(pipeline_data)

    # PATCH /api/leads/{id}/move-stage/
    @action(detail=True, methods=['patch'], url_path='move-stage')
    def move_stage(self, request, pk=None):
        lead = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response({"error": "status field is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = lead.status
        lead.status = new_status
        lead.save()
        
        # Log activity
        LeadActivityTimeline.objects.create(
            lead=lead,
            user=request.user,
            activity_type='Status Change',
            description=f"Moved lead status from '{old_status}' to '{new_status}'."
        )
        
        return Response(LeadSerializer(lead, context={'request': request}).data)

    # GET /api/leads/{id}/activities/ or POST /api/leads/{id}/activities/
    @action(detail=True, methods=['get', 'post'], url_path='activities')
    def activities(self, request, pk=None):
        lead = self.get_object()
        if request.method == 'GET':
            timeline = lead.activities.all().order_by('-created_at')
            serializer = LeadActivityTimelineSerializer(timeline, many=True)
            return Response(serializer.data)
            
        elif request.method == 'POST':
            serializer = LeadActivityTimelineSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(lead=lead, user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # POST /api/leads/{id}/convert/
    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None):
        lead = self.get_object()
        if lead.status == 'Won':
            return Response({"detail": "Lead is already won and converted."}, status=status.HTTP_400_BAD_REQUEST)
            
        lead.status = 'Won'
        lead.save()
        
        # Create Client
        client = Client.objects.create(
            company_name=lead.company_name,
            industry=lead.industry,
            website=lead.website,
            status='Active',
            account_manager=lead.assigned_to,
            created_by=request.user,
            notes=lead.notes
        )
        
        # Create Contact for Client
        client_contact = ClientContact.objects.create(
            client=client,
            name=lead.contact_person,
            email=lead.email,
            phone=lead.phone,
            is_primary=True
        )
        
        # Log activity
        LeadActivityTimeline.objects.create(
            lead=lead,
            user=request.user,
            activity_type='Status Change',
            description=f"Converted Lead to Client: {client.company_name}"
        )
        
        return Response({
            "detail": "Lead converted successfully.",
            "client_id": client.id,
            "contact_id": client_contact.id
        }, status=status.HTTP_200_OK)

    # GET /api/leads/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        leads = self.filter_queryset(self.get_queryset())
        
        total_leads = leads.count()
        leads_by_status = leads.values('status').annotate(count=Count('id'))
        leads_by_source = leads.values('lead_source').annotate(count=Count('id'))
        
        total_value = leads.aggregate(total_val=Sum('estimated_value'))['total_val'] or 0.0
        
        return Response({
            "total_leads": total_leads,
            "total_value": total_value,
            "leads_by_status": leads_by_status,
            "leads_by_source": leads_by_source
        })

    # POST /api/leads/bulk-assign/
    @action(detail=False, methods=['post'], url_path='bulk-assign')
    def bulk_assign(self, request):
        lead_ids = request.data.get('lead_ids', [])
        user_id = request.data.get('user_id')
        
        if not lead_ids or not user_id:
            return Response({"error": "lead_ids and user_id fields are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        leads = Lead.objects.filter(id__in=lead_ids)
        leads.update(assigned_to_id=user_id)
        
        # Log activity for each lead
        for lead in leads:
            LeadActivityTimeline.objects.create(
                lead=lead,
                user=request.user,
                activity_type='Follow-up',
                description=f"Reassigned lead to user ID: {user_id}"
            )
            
        return Response({"detail": f"Successfully reassigned {leads.count()} leads."}, status=status.HTTP_200_OK)
