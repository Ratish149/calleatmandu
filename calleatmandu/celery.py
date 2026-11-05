import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "calleatmandu.settings")

app = Celery("calleatmandu")

# Read configuration from Django settings, using the CELERY_ namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks.py modules in all installed apps.
app.autodiscover_tasks()
