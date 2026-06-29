from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.projects.models import Project
from apps.clients.models import Client

class SEOKeyword(models.Model):
    ENGINE_CHOICES = (
        ('Google', 'Google'),
        ('Bing', 'Bing'),
    )
    STATUS_CHOICES = (
        ('Tracking', 'Tracking'),
        ('Not Tracking', 'Not Tracking'),
    )
    keyword = models.CharField(max_length=255)
    target_url = models.URLField()
    search_engine = models.CharField(max_length=20, choices=ENGINE_CHOICES, default='Google')
    country = models.CharField(max_length=10, default='US')
    language = models.CharField(max_length=10, default='en')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='seo_keywords')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='seo_keywords')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_keywords')
    current_position = models.IntegerField(default=0)
    best_position = models.IntegerField(default=0)
    monthly_search_volume = models.IntegerField(default=0)
    difficulty = models.IntegerField(default=0) # 1-100
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Tracking')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.keyword} ({self.target_url})"


class SEORankLog(models.Model):
    keyword = models.ForeignKey(SEOKeyword, on_delete=models.CASCADE, related_name='rank_logs')
    position = models.IntegerField()
    check_date = models.DateField(default=timezone.now)
    url_ranking = models.URLField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update current & best position in parent keyword
        kw = self.keyword
        kw.current_position = self.position
        if kw.best_position == 0 or self.position < kw.best_position:
            kw.best_position = self.position
        kw.save()

    def __str__(self):
        return f"{self.keyword.keyword} - Pos {self.position} on {self.check_date}"


class SEOReport(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='seo_reports')
    report_date = models.DateField()
    organic_traffic = models.IntegerField(default=0)
    organic_clicks = models.IntegerField(default=0)
    impressions = models.IntegerField(default=0)
    avg_position = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    backlinks_total = models.IntegerField(default=0)
    new_backlinks = models.IntegerField(default=0)
    lost_backlinks = models.IntegerField(default=0)
    top_pages = models.JSONField(default=list, blank=True)
    issues_found = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    pdf_file = models.FileField(upload_to='seo_reports/', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SEO Report for {self.client.company_name} - {self.report_date}"
