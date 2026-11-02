from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0002_reminderlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemNotificationSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_automation_enabled', models.BooleanField(default=True, help_text='Master switch: if False, automated emails (reminders, cron jobs, notifications) are paused.')),
                ('email_automation_disabled_reason', models.CharField(blank=True, default='Turned off by Administrator', max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_notification_settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'System Notification Setting',
                'verbose_name_plural': 'System Notification Settings',
            },
        ),
    ]

