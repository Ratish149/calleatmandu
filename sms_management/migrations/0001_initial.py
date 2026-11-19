import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("order", "0022_order_only_save"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SMSLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("phone_number", models.CharField(max_length=20)),
                ("message", models.TextField()),
                ("sender_id", models.CharField(blank=True, default="", max_length=50)),
                ("job_id", models.CharField(blank=True, default="", max_length=100)),
                (
                    "scheduled_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When this SMS should be sent (30 minutes after delivery).",
                        null=True,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("cost", models.FloatField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_logs_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_logs",
                        to="order.order",
                    ),
                ),
            ],
            options={
                "verbose_name": "SMS Log",
                "verbose_name_plural": "SMS Logs",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["order", "status"],
                        name="sms_managem_order_i_7a1c2d_idx",
                    ),
                    models.Index(
                        fields=["status", "scheduled_at"],
                        name="sms_managem_status_4b9e1f_idx",
                    ),
                ],
            },
        ),
    ]
