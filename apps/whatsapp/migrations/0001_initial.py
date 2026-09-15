from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("wa_id", models.CharField(db_index=True, max_length=32, unique=True)),
                ("profile_name", models.CharField(blank=True, max_length=255)),
                ("last_message_at", models.DateTimeField(blank=True, null=True)),
                ("last_message_preview", models.CharField(blank=True, max_length=500)),
                ("unread_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-last_message_at", "-updated_at"]},
        ),
        migrations.CreateModel(
            name="WhatsAppMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("wamid", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                (
                    "direction",
                    models.CharField(choices=[("in", "Incoming"), ("out", "Outgoing")], max_length=8),
                ),
                ("message_type", models.CharField(default="text", max_length=40)),
                ("text", models.TextField(blank=True)),
                ("media_id", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("sent", "Sent"),
                            ("delivered", "Delivered"),
                            ("read", "Read"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("timestamp", models.DateTimeField()),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="whatsapp.whatsappcontact",
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="whatsapp_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["timestamp", "id"]},
        ),
        migrations.AddIndex(
            model_name="whatsappmessage",
            index=models.Index(fields=["contact", "timestamp"], name="whatsapp_wh_contact_ts_idx"),
        ),
    ]
