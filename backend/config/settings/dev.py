"""Local development settings.

Runs against the Docker Compose stack. Differs from production only in
verbosity and host checking — the server, the database, the cache and the
search engine are the same as deployed, so a launch bug reproduces locally.
"""

from __future__ import annotations

from config.settings.base import *  # noqa: F403
from config.settings.env import get_bool, get_list

DEBUG = get_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = get_list(
    "DJANGO_ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "backend", "nginx", "testserver"],
)

# Nginx terminates plain HTTP locally, so cookies cannot be Secure-only or the
# browser would discard them. Production overrides all three.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

CSRF_TRUSTED_ORIGINS = get_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ["http://localhost:8080", "http://127.0.0.1:8080"],
)

# Full SQL in the console when explicitly asked for; off by default because the
# reader issues many small queries and the noise buries everything else.
if get_bool("DJANGO_LOG_SQL", False):
    LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"  # noqa: F405
