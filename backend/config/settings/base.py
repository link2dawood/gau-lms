"""Settings shared by every environment.

Environment-specific modules (``dev``, ``prod``, ``test``) import everything
from here and override only what genuinely differs. Anything that must not
differ between a developer machine and the server — the default-deny
permission policy, the content model's storage assumptions, module boundaries —
belongs here and nowhere else.
"""

from __future__ import annotations

from pathlib import Path

from config.settings.env import (
    get_int,
    get_list,
    get_str,
    parse_database_url,
    parse_redis_url,
    require_str,
)

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = require_str("DJANGO_SECRET_KEY")

# Off unless an environment deliberately turns it on. A missing DJANGO_DEBUG
# must never mean "debug".
DEBUG = False

ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", [])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AUTH_USER_MODEL is deliberately NOT set here. Canvas is the authority for
# identity (architecture rule C.5), so the platform's user record carries
# Canvas fields and will be a custom model — but Django resolves
# AUTH_USER_MODEL eagerly during system checks, so it can only be declared once
# apps.accounts exists.
#
# Task 1.1 creates apps.accounts.User, sets AUTH_USER_MODEL here, and runs the
# first migration in the same change. NO MIGRATION MAY BE APPLIED BEFORE THEN:
# migrating now would bake django.contrib.auth's default User into the
# migration state and turn a one-line setting into a data migration.
# See DECISIONS.md D-009.

# ---------------------------------------------------------------------------
# Applications
#
# Bounded modules per architecture rule C.1. Cross-app access goes through a
# module's services.py, never by importing another app's models directly.
# Each app is added by the task that creates it.
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
]

THIRD_PARTY_APPS = [
    "rest_framework",
]

LOCAL_APPS: list[str] = [
    # "apps.accounts",    task 1.1
    # "apps.lti",         task 1.2
    # "apps.courses",     task 1.6
    # "apps.content",     task 2.1
    # "apps.versioning",  task 2.4
    # "apps.reader",      task 2.9
    # "apps.search",      task 2.11
    # "apps.cms",         task 3.1
    # "apps.imports",     task 3.11
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # apps.lti.middleware.CourseScopeMiddleware is inserted by task 1.11.
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {"default": parse_database_url(require_str("DATABASE_URL"))}

# ---------------------------------------------------------------------------
# Cache, sessions and Celery
#
# Four logical Redis databases, separated by purpose (DECISIONS.md D-008):
# clearing the cache must not drop a queued import or an in-flight LTI nonce.
# ---------------------------------------------------------------------------

REDIS_CACHE_URL = parse_redis_url(require_str("REDIS_CACHE_URL"))
LTI_STATE_REDIS_URL = parse_redis_url(require_str("LTI_STATE_REDIS_URL"))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "KEY_PREFIX": "gau",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_NAME = "gau_session"
# A Canvas launch is a working session, not a long-lived login. Task 1.9
# narrows the cookie further for the iframe context.
SESSION_COOKIE_AGE = get_int("SESSION_COOKIE_AGE", 60 * 60 * 12)
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True

CELERY_BROKER_URL = parse_redis_url(require_str("CELERY_BROKER_URL"))
CELERY_RESULT_BACKEND = parse_redis_url(require_str("CELERY_RESULT_BACKEND"))
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = get_int("CELERY_TASK_TIME_LIMIT", 30 * 60)
CELERY_TASK_SOFT_TIME_LIMIT = get_int("CELERY_TASK_SOFT_TIME_LIMIT", 25 * 60)
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = "UTC"

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

MEILISEARCH_URL = require_str("MEILISEARCH_URL")
MEILISEARCH_API_KEY = require_str("MEILI_MASTER_KEY")
# Namespaced so staging and production can share a Meilisearch instance without
# one reindex clobbering the other's documents.
MEILISEARCH_INDEX_PREFIX = get_str("MEILISEARCH_INDEX_PREFIX", "gau") or "gau"

# ---------------------------------------------------------------------------
# REST framework
#
# Default deny (architecture rule C.8). A view that forgets to declare a
# permission class inherits IsAuthenticated rather than public access. The one
# deliberate exception is the health endpoint, which declares AllowAny
# explicitly.
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
}

# ---------------------------------------------------------------------------
# Passwords
#
# Platform accounts are provisioned from Canvas and carry no usable password
# (task 1.8). These validators apply only to locally managed staff accounts.
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = get_str("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = get_str("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media
#
# Nginx serves both directly from the shared volumes (docker/nginx/conf.d).
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Imported source documents are the largest uploads accepted. Kept in step with
# client_max_body_size in docker/nginx/nginx.conf.
DATA_UPLOAD_MAX_MEMORY_SIZE = get_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 64 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = get_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)

# ---------------------------------------------------------------------------
# Proxy awareness
#
# Every request arrives through Nginx. Django must read the original scheme to
# build correct absolute URLs and to decide whether a cookie may be marked
# Secure — which a Canvas iframe launch depends on (task 1.9).
# ---------------------------------------------------------------------------

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ---------------------------------------------------------------------------
# Logging
#
# Everything to stdout in one line per event, for `docker compose logs` locally
# and the platform's log collector on the server. Never to a file inside the
# container.
# ---------------------------------------------------------------------------

LOG_LEVEL = get_str("DJANGO_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        # Launch outcomes are security-relevant and audited separately
        # (task 1.15); this logger carries the operational detail.
        "apps.lti": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

# Public origin of the tool, used to build LTI redirect URIs and the JWKS URL
# handed to the Canvas administrator (task 1.17).
PLATFORM_BASE_URL = require_str("PLATFORM_BASE_URL").rstrip("/")

# Canvas hosts permitted to embed the reader in an iframe. Enforced as a
# Content-Security-Policy frame-ancestors directive in task 4.4.
CANVAS_FRAME_ANCESTORS = get_list("CANVAS_FRAME_ANCESTORS", [])

APPEND_SLASH = True
X_FRAME_OPTIONS = "DENY"  # relaxed for the launch routes only, in task 4.4
