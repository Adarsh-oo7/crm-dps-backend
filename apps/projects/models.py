from django.db import models
from django.conf import settings
from apps.clients.models import Client

class Project(models.Model):
    PROJECT_TYPE_CHOICES = (
        ('Web Development', 'Web Development'),
        ('Mobile App', 'Mobile App'),
        ('SEO', 'SEO'),
        ('Digital Marketing', 'Digital Marketing'),
        ('UI/UX Design', 'UI/UX Design'),
        ('Software', 'Software'),
        ('In-house Product', 'In-house Product'),
        ('Other', 'Other'),
    )

    STATUS_CHOICES = (
        ('Backlog', 'Backlog'),
        ('Planning', 'Planning'),
        ('UI Design', 'UI Design'),
        ('Development', 'Development'),
        ('Testing', 'Testing'),
        ('Deployment', 'Deployment'),
        ('Completed', 'Completed'),
        ('On Hold', 'On Hold'),
        ('Cancelled', 'Cancelled'),
    )

    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    )

    BUDGET_TYPE_CHOICES = (
        ('Fixed', 'Fixed'),
        ('Hourly', 'Hourly'),
    )

    name = models.CharField(max_length=255)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    
    project_type = models.CharField(max_length=50, choices=PROJECT_TYPE_CHOICES, default='Web Development')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Planning')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects'
    )
    
    team_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='assigned_projects'
    )
    
    start_date = models.DateField(blank=True, null=True)
    deadline = models.DateField(blank=True, null=True)
    actual_completion_date = models.DateField(blank=True, null=True)
    
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='USD')
    budget_type = models.CharField(max_length=20, choices=BUDGET_TYPE_CHOICES, default='Fixed')
    
    hours_estimated = models.IntegerField(default=0)
    
    description = models.TextField(blank=True, null=True)
    tech_stack = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    github_repo = models.URLField(blank=True, null=True)
    staging_url = models.URLField(blank=True, null=True)
    live_url = models.URLField(blank=True, null=True)
    figma_url = models.URLField(blank=True, null=True)
    
    completion_percentage = models.IntegerField(default=0) # 0-100
    notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_projects'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def hours_logged(self):
        # Calculated from time logs in future tasks module integration
        try:
            return sum(task.logged_hours for task in self.tasks.all())
        except Exception:
            return 0.00


class Milestone(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Delayed', 'Delayed'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='milestones'
    )
    
    completion_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.project.name}"
