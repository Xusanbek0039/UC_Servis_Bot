from .base import *

DEBUG = True

# In development, allow all hosts
ALLOWED_HOSTS = ["*"]

# If Redis is not available locally in development, fallback to LocMemCache
try:
    import redis
    r = redis.from_url(REDIS_URL, socket_timeout=1)
    r.ping()
except Exception:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
    # Use in-memory task execution for development when Redis/Celery is offline
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
