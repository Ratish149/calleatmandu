from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "sms_management",
            "0002_rename_sms_managem_order_i_7a1c2d_idx_sms_managem_order_i_7e92d8_idx_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="SMSSettings",
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
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="If unchecked, no post-delivery SMS will be scheduled.",
                    ),
                ),
                (
                    "delay_minutes",
                    models.PositiveIntegerField(
                        default=30,
                        help_text="Minutes to wait after delivery before sending the SMS.",
                    ),
                ),
                (
                    "message_template",
                    models.TextField(
                        default=(
                            "Dear {customer_name}, how was your CallEatMandu order "
                            "#{order_number}? We hope you enjoyed your meal. Thank you!"
                        ),
                        help_text=(
                            "Message body. Placeholders: {customer_name}, {order_number}. "
                            "Max ~720 characters for NestSMS text encoding."
                        ),
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "SMS Settings",
                "verbose_name_plural": "SMS Settings",
            },
        ),
    ]
