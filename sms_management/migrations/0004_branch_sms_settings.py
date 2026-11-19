import django.db.models.deletion
from django.db import migrations, models


def clear_legacy_singleton_settings(apps, schema_editor):
    """Remove old singleton SMSSettings rows before requiring branch."""
    SMSSettings = apps.get_model("sms_management", "SMSSettings")
    SMSSettings.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("user_account", "0010_alter_user_role"),
        ("sms_management", "0003_smssettings"),
    ]

    operations = [
        migrations.RunPython(clear_legacy_singleton_settings, migrations.RunPython.noop),
        migrations.AddField(
            model_name="smslog",
            name="branch",
            field=models.ForeignKey(
                blank=True,
                help_text="Branch that owned the order when SMS was scheduled.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sms_logs",
                to="user_account.branch",
            ),
        ),
        migrations.AddField(
            model_name="smssettings",
            name="branch",
            field=models.OneToOneField(
                help_text="Branch this SMS configuration belongs to.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sms_settings",
                to="user_account.branch",
            ),
        ),
        migrations.AddField(
            model_name="smssettings",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name="smssettings",
            name="is_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Approve this branch for post-delivery SMS. "
                    "If unchecked, orders from this branch will not trigger SMS."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="smssettings",
            name="message_template",
            field=models.TextField(
                default=(
                    "Dear {customer_name}, how was your CallEatMandu order #{order_number}? "
                    "We hope you enjoyed your meal. Thank you!"
                ),
                help_text=(
                    "Message body for this branch. Placeholders: {customer_name}, "
                    "{order_number}. Max ~720 characters for NestSMS text encoding."
                ),
            ),
        ),
        migrations.AlterModelOptions(
            name="smssettings",
            options={
                "ordering": ["branch__name"],
                "verbose_name": "SMS Settings",
                "verbose_name_plural": "SMS Settings",
            },
        ),
        migrations.AddIndex(
            model_name="smslog",
            index=models.Index(
                fields=["branch", "status"],
                name="sms_managem_branch_status_idx",
            ),
        ),
    ]
