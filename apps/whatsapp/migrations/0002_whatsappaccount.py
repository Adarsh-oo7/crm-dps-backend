from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("whatsapp", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("waba_id", models.CharField(blank=True, max_length=32)),
                ("phone_number_id", models.CharField(max_length=32)),
                ("display_phone_number", models.CharField(blank=True, max_length=32)),
                ("verified_name", models.CharField(blank=True, max_length=255)),
                ("business_id", models.CharField(blank=True, max_length=32)),
                ("access_token", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("raw_session", models.JSONField(blank=True, default=dict)),
                ("connected_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connected_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="whatsapp_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-connected_at"]},
        ),
    ]
