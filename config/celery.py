import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("pubg_uc_bot")

# Load config from Django settings with CELERY namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Periodic Tasks
app.conf.beat_schedule = {
    "cancel-expired-pending-orders": {
        "task": "apps.orders.tasks.cancel_expired_orders",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "retry-failed-topups": {
        "task": "apps.orders.tasks.retry_failed_topups",
        "schedule": crontab(minute="*/3"),  # Every 3 minutes
    },
}
