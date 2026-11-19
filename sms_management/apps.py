from django.apps import AppConfig


class SmsManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sms_management"
    verbose_name = "SMS Management"

    def ready(self):
        import sms_management.signals  # noqa: F401
