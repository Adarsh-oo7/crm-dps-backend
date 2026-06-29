from django.db import models
from django.conf import settings

class KnowledgeArticle(models.Model):
    CATEGORY_CHOICES = (
        ('SOP', 'SOP'),
        ('Checklist', 'Checklist'),
        ('Template', 'Template'),
        ('Guide', 'Guide'),
        ('Policy', 'Policy'),
        ('Credential', 'Credential'),
        ('Other', 'Other'),
    )
    VISIBILITY_CHOICES = (
        ('All', 'All'),
        ('Admin Only', 'Admin Only'),
        ('Specific Roles', 'Specific Roles'),
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Guide')
    content = models.TextField()
    is_confidential = models.BooleanField(default=False)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='All')
    allowed_roles = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='authored_articles')
    last_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_articles')
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
