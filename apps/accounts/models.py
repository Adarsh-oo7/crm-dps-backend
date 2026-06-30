from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'superadmin')
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('developer', 'Developer'),
        ('designer', 'Designer'),
        ('marketer', 'Marketer'),
        ('support', 'Support'),
        ('finance', 'Finance'),
    )
    
    # Disable default username, use email as unique identifier
    username = None
    email = models.EmailField(unique=True)
    
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='developer')
    department = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    fcm_token = models.CharField(max_length=255, blank=True)
    whatsapp_number = models.CharField(max_length=50, blank=True)
    notification_preferences = models.JSONField(default=dict, blank=True)
    custom_permissions = models.JSONField(default=list, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    def __str__(self):
        return f"{self.email} ({self.role})"


class Attendance(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Half Day', 'Half Day'),
        ('WFH', 'WFH'),
        ('Leave', 'Leave'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(auto_now_add=True)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    duration_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Present')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if getattr(self, '_skip_recalc', False):
            super().save(*args, **kwargs)
            return
            
        if self.check_in and self.check_out:
            import datetime
            h1, m1, s1 = self.check_in.hour, self.check_in.minute, self.check_in.second
            h2, m2, s2 = self.check_out.hour, self.check_out.minute, self.check_out.second
            t1 = datetime.timedelta(hours=h1, minutes=m1, seconds=s1)
            t2 = datetime.timedelta(hours=h2, minutes=m2, seconds=s2)
            duration = t2 - t1
            self.duration_hours = max(0.0, duration.total_seconds() / 3600.0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.date} - {self.status}"


class LeaveRequest(models.Model):
    LEAVE_TYPES = (
        ('Annual', 'Annual'),
        ('Sick', 'Sick'),
        ('Casual', 'Casual'),
        ('Maternity', 'Maternity'),
        ('Other', 'Other'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, default='Annual')
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.IntegerField(editable=False, default=1)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        delta = self.end_date - self.start_date
        self.days_requested = max(1, delta.days + 1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.leave_type} ({self.start_date} to {self.end_date})"


class DailyWorkLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_logs')
    date = models.DateField(auto_now_add=True)
    log_text = models.TextField()
    tasks_completed = models.JSONField(default=list, blank=True)
    blockers = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.date}"


class UserOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50, default='login')  # 'login' or 'password_change'
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_valid(self):
        from django.utils import timezone
        import datetime
        return not self.is_verified and (timezone.now() - self.created_at) < datetime.timedelta(minutes=10)

    def __str__(self):
        return f"{self.user.email} - {self.otp} - {self.purpose}"


