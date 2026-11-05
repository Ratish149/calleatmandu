from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _tune_sqlite_connection(sender, connection, **kwargs):
    """Enable WAL + a busy timeout so the Celery worker and web process can
    share a SQLite database without immediate 'database is locked' errors."""
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")


class CommonConfig(AppConfig):
    name = "common"

    def ready(self):
        connection_created.connect(_tune_sqlite_connection)
