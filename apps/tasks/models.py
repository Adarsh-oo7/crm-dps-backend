from django.db import models
from django.conf import settings
from apps.projects.models import Project
from apps.clients.models import Client

class Task(models.Model):
    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
        ('Blocker', 'Blocker'),
    )

    STATUS_CHOICES = (
        ('Todo', 'Todo'),
        ('In Progress', 'In Progress'),
        ('In Review', 'In Review'),
        ('Blocked', 'Blocked'),
        ('Done', 'Done'),
        ('Cancelled', 'Cancelled'),
    )

    TASK_TYPE_CHOICES = (
        ('Development', 'Development'),
        ('Design', 'Design'),
        ('Testing', 'Testing'),
        ('Marketing', 'Marketing'),
        ('SEO', 'SEO'),
        ('Meeting', 'Meeting'),
        ('Documentation', 'Documentation'),
        ('Support', 'Support'),
        ('Other', 'Other'),
    )

    RECURRING_FREQUENCY_CHOICES = (
        ('Daily', 'Daily'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True) # Rich text or standard text
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks', blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='tasks', blank=True, null=True)
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegated_tasks'
    )
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Todo')
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES, default='Development')
    
    due_date = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    tags = models.JSONField(default=list, blank=True)
    
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20, 
        choices=RECURRING_FREQUENCY_CHOICES, 
        blank=True, 
        null=True
    )
    
    parent_task = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        related_name='subtasks', 
        blank=True, 
        null=True
    )
    
    order = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def logged_hours(self):
        total_minutes = self.timelogs.aggregate(
            total=models.Sum('duration_minutes')
        )['total'] or 0
        return round(total_minutes / 60.0, 2)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_assigned_to = None
        if not is_new:
            try:
                old_assigned_to = Task.objects.get(pk=self.pk).assigned_to
            except Task.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        if self.assigned_to and (is_new or old_assigned_to != self.assigned_to):
            try:
                from apps.notifications.models import Notification
                assigned_by_name = (
                    self.assigned_by.full_name if (self.assigned_by and self.assigned_by.full_name)
                    else (self.assigned_by.email if self.assigned_by else "System")
                )
                Notification.objects.create(
                    user=self.assigned_to,
                    title="New Task Assigned",
                    message=f"You have been assigned a new task: '{self.title}' by {assigned_by_name}.",
                    notification_type="Task",
                    related_url="/tasks"
                )
            except Exception as e:
                # Don't fail the save if notification fails
                pass


class TaskChecklistItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    text = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.text} ({self.task.title})"


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    attachment = models.FileField(upload_to='task_comments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.user.email} on {self.task.title}"


class TaskTimeLog(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='timelogs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_minutes = models.IntegerField(default=0) # duration in minutes
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TimeLog by {self.user.email} - {self.duration_minutes}m ({self.task.title})"

    def save(self, *args, **kwargs):
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            self.duration_minutes = max(0, int(delta.total_seconds() / 60.0))
        super().save(*args, **kwargs)


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/')
    filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.task.title})"
