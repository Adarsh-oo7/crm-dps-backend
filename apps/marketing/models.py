from django.db import models
from django.conf import settings

class Campaign(models.Model):
    TYPE_CHOICES = (
        ('Email', 'Email'),
        ('Social Media', 'Social Media'),
        ('Google Ads', 'Google Ads'),
        ('WhatsApp', 'WhatsApp'),
        ('Content', 'Content'),
        ('SEO', 'SEO'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Planning', 'Planning'),
        ('Active', 'Active'),
        ('Paused', 'Paused'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )
    PLATFORM_CHOICES = (
        ('Facebook', 'Facebook'),
        ('Instagram', 'Instagram'),
        ('LinkedIn', 'LinkedIn'),
        ('Google', 'Google'),
        ('Twitter', 'Twitter'),
        ('Other', 'Other'),
    )
    name = models.CharField(max_length=255)
    campaign_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Planning')
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    actual_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    target_audience = models.TextField(blank=True)
    goal = models.TextField(blank=True)
    expected_reach = models.IntegerField(default=0)
    actual_reach = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def roi(self):
        if self.actual_spent > 0 and self.conversions > 0:
            # Let's say estimated conversion value is $100 per conversion for simplicity, or just returns conversions / spent ratio
            return float(self.conversions * 100) / float(self.actual_spent)
        return 0.0

    def __str__(self):
        return self.name


class ContentCalendarItem(models.Model):
    CONTENT_TYPE_CHOICES = (
        ('Blog', 'Blog'),
        ('LinkedIn Post', 'LinkedIn Post'),
        ('Instagram', 'Instagram'),
        ('Twitter', 'Twitter'),
        ('Video', 'Video'),
        ('Email Newsletter', 'Email Newsletter'),
        ('Case Study', 'Case Study'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Idea', 'Idea'),
        ('Draft', 'Draft'),
        ('In Review', 'In Review'),
        ('Scheduled', 'Scheduled'),
        ('Published', 'Published'),
    )
    title = models.CharField(max_length=255)
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPE_CHOICES)
    platform = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Idea')
    scheduled_date = models.DateTimeField(null=True, blank=True)
    published_date = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='authored_content')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_content')
    content_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    engagement_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
