from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from apps.leads.models import Lead, LeadActivityTimeline
from apps.clients.models import Client, ClientContact
from apps.projects.models import Project, Milestone
from apps.tasks.models import Task, TaskChecklistItem
from apps.followups.models import FollowUp
from django.utils import timezone
import datetime

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with mock data for DPS OS'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding mock data...')
        
        # 1. Seed Users
        password = make_password('adminpass')
        
        users_data = [
            {'email': 'manager@digitalprod.com', 'full_name': 'Sarah Manager', 'role': 'manager', 'department': 'Sales'},
            {'email': 'dev@digitalprod.com', 'full_name': 'Alex Developer', 'role': 'developer', 'department': 'Engineering'},
            {'email': 'designer@digitalprod.com', 'full_name': 'Emma Designer', 'role': 'designer', 'department': 'Design'},
            {'email': 'finance@digitalprod.com', 'full_name': 'Bob Finance', 'role': 'finance', 'department': 'Finance'},
        ]
        
        seeded_users = {}
        for u in users_data:
            user, created = User.objects.get_or_create(
                email=u['email'],
                defaults={
                    'full_name': u['full_name'],
                    'role': u['role'],
                    'department': u['department'],
                    'password': password,
                    'is_active': True
                }
            )
            seeded_users[u['role']] = user
            
        admin_user = User.objects.filter(role='superadmin').first()
        seeded_users['superadmin'] = admin_user
        
        # 2. Seed Leads
        leads_data = [
            {'company_name': 'Acme Corp', 'contact_person': 'John Doe', 'email': 'john@acme.com', 'phone': '1234567890', 'status': 'New', 'priority': 'High', 'value': 5000.00},
            {'company_name': 'Stark Industries', 'contact_person': 'Pepper Potts', 'email': 'pepper@stark.com', 'phone': '9876543210', 'status': 'Meeting Scheduled', 'priority': 'Hot', 'value': 25000.00},
            {'company_name': 'Wayne Enterprises', 'contact_person': 'Lucius Fox', 'email': 'lucius@wayne.com', 'phone': '555123456', 'status': 'Proposal Sent', 'priority': 'Hot', 'value': 50000.00},
            {'company_name': 'Initech Inc', 'contact_person': 'Peter Gibbons', 'email': 'peter@initech.com', 'phone': '444555666', 'status': 'Contacted', 'priority': 'Low', 'value': 2000.00},
        ]
        
        for l in leads_data:
            lead, created = Lead.objects.get_or_create(
                company_name=l['company_name'],
                defaults={
                    'contact_person': l['contact_person'],
                    'email': l['email'],
                    'phone': l['phone'],
                    'status': l['status'],
                    'priority': l['priority'],
                    'estimated_value': l['value'],
                    'assigned_to': seeded_users['manager'],
                    'created_by': admin_user
                }
            )
            if created:
                LeadActivityTimeline.objects.create(
                    lead=lead,
                    user=admin_user,
                    activity_type='Note',
                    description=f"Initialized lead for {lead.company_name}."
                )

        # 3. Seed Clients
        clients_data = [
            {'company_name': 'Globex Corporation', 'contact_person': 'Hank Scorpio', 'email': 'hank@globex.com', 'status': 'Active'},
            {'company_name': 'Umbrella Corp', 'contact_person': 'Albert Wesker', 'email': 'wesker@umbrella.com', 'status': 'On Hold'},
        ]
        
        seeded_clients = []
        for c in clients_data:
            client, created = Client.objects.get_or_create(
                company_name=c['company_name'],
                defaults={
                    'status': c['status'],
                    'account_manager': seeded_users['manager'],
                    'created_by': admin_user
                }
            )
            seeded_clients.append(client)
            if created:
                ClientContact.objects.get_or_create(
                    client=client,
                    name=c['contact_person'],
                    defaults={
                        'email': c['email'],
                        'is_primary': True
                    }
                )

        # 4. Seed Projects
        projects_data = [
            {'name': 'Globex E-Commerce Platform', 'client': seeded_clients[0], 'status': 'Development', 'priority': 'High', 'budget': 15000.00},
            {'name': 'Umbrella Portal Security', 'client': seeded_clients[1], 'status': 'Planning', 'priority': 'Critical', 'budget': 35000.00},
        ]
        
        seeded_projects = []
        for p in projects_data:
            project, created = Project.objects.get_or_create(
                name=p['name'],
                client=p['client'],
                defaults={
                    'status': p['status'],
                    'priority': p['priority'],
                    'budget': p['budget'],
                    'project_manager': seeded_users['manager'],
                    'created_by': admin_user
                }
            )
            seeded_projects.append(project)
            if created:
                project.team_members.add(seeded_users['developer'], seeded_users['designer'])
                
                # Add milestone
                Milestone.objects.create(
                    project=project,
                    title='UI Layout Signoff',
                    due_date=timezone.now() + timezone.timedelta(days=7),
                    status='In Progress',
                    assigned_to=seeded_users['designer']
                )

        # 5. Seed Tasks
        tasks_data = [
            {'title': 'Draft database schema', 'project': seeded_projects[0], 'status': 'In Progress', 'priority': 'High'},
            {'title': 'Create landing page mockups', 'project': seeded_projects[0], 'status': 'In Review', 'priority': 'Medium'},
            {'title': 'Audit security constraints', 'project': seeded_projects[1], 'status': 'Todo', 'priority': 'Critical'},
        ]
        
        for t in tasks_data:
            task, created = Task.objects.get_or_create(
                title=t['title'],
                project=t['project'],
                defaults={
                    'status': t['status'],
                    'priority': t['priority'],
                    'assigned_to': seeded_users['developer'] if t['priority'] == 'High' else seeded_users['designer'],
                    'created_by': admin_user,
                    'due_date': timezone.now() + timezone.timedelta(days=3)
                }
            )
            if created:
                TaskChecklistItem.objects.create(
                    task=task,
                    text='First subtask item',
                    is_completed=False
                )

        # 6. Seed Followups
        FollowUp.objects.get_or_create(
            title='Intro call with Stark Industries',
            defaults={
                'follow_up_type': 'Call',
                'related_to_type': 'Lead',
                'related_to_id': Lead.objects.filter(company_name='Stark Industries').first().id,
                'scheduled_at': timezone.now() + timezone.timedelta(hours=2),
                'assigned_to': seeded_users['manager'],
                'created_by': admin_user,
                'status': 'Pending'
            }
        )
        
        FollowUp.objects.get_or_create(
            title='Send agreement draft to Globex Scorpio',
            defaults={
                'follow_up_type': 'Email',
                'related_to_type': 'Client',
                'related_to_id': seeded_clients[0].id,
                'scheduled_at': timezone.now() + timezone.timedelta(days=1),
                'assigned_to': seeded_users['manager'],
                'created_by': admin_user,
                'status': 'Pending'
            }
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded mock data!'))
