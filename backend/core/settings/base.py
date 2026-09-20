"""Settings shared by every environment.

Environment-specific modules (``dev``, ``prod``, ``test``) import everything
from here and override only what genuinely differs. Anything that must not
differ between a developer machine and the server — the default-deny
permission policy, the content model's storage assumptions, module boundaries —
belongs here and nowhere else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from psycopg import IsolationLevel

from core.settings.env import (
    get_int,
    get_list,
    get_str,
    parse_database_url,
    parse_redis_url,
    require_str,
)

# backend/core/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = require_str("DJANGO_SECRET_KEY")

# Off unless an environment deliberately turns it on. A missing DJANGO_DEBUG
# must never mean "debug".
DEBUG = False

ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", [])

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Canvas is the authority for identity (architecture rule C.5), so the user
# record is the platform's own model, keyed on the Canvas identity, with no
# usable password for readers. Declared together with the model and its first
# migration (DECISIONS.md D-009).
AUTH_USER_MODEL = "accounts.User"

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

# Still to come, each added by the task that builds it: versioning (2.4),
# reader (2.9), search (2.11), cms (3.1), imports (3.11). Each needs a
# MIGRATION_MODULES entry in the same change.
LOCAL_APPS: list[str] = [
    "apps.accounts",
    "apps.lti",
    "apps.courses",
    "apps.content",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Migrations live in one place, backend/migrations/<app label>/, rather than
# inside each app (DECISIONS.md D-024). Django only looks there because of this
# mapping: an app added to LOCAL_APPS without an entry here is silently treated
# as having no migrations, and its tables are never created.
MIGRATION_MODULES = {
    "accounts": "migrations.accounts",
    "lti": "migrations.lti",
    "courses": "migrations.courses",
    "content": "migrations.content",
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # After authentication, deliberately: a course scope without an
    # authenticated user is meaningless, and treating one as valid would
    # hand a course context to an anonymous request.
    "apps.lti.middleware.CourseScopeMiddleware",
]

# Note before adding a CORS layer here: POST /lti/session/ is exempt from
# Django's CSRF check and relies on a custom request header that a
# cross-site form cannot set and a cross-origin fetch cannot get past a
# preflight this origin does not answer. A permissive CORS_ALLOW_HEADERS
# would remove that defence with nothing failing (D-038).

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

# Pin the isolation level rather than inheriting whatever the server or a
# connection pooler has as its default.
#
# Launch provisioning depends on READ COMMITTED semantics: when two first
# launches race, the loser's INSERT blocks on the winner's uncommitted row and
# only raises once the winner has committed — so the re-read that follows can
# see it. Under REPEATABLE READ the whole transaction shares one snapshot taken
# before that commit, the re-read finds nothing, and a legitimate launch fails.
# See utils/db.py and DECISIONS.md D-034.
DATABASES["default"].setdefault("OPTIONS", {})["isolation_level"] = IsolationLevel.READ_COMMITTED

# ---------------------------------------------------------------------------
# Cache, sessions and Celery
#
# Four logical Redis databases, separated by purpose (DECISIONS.md D-008):
# clearing the cache must not drop a queued import or an in-flight LTI nonce.
# ---------------------------------------------------------------------------

REDIS_CACHE_URL = parse_redis_url(require_str("REDIS_CACHE_URL"))
LTI_STATE_REDIS_URL = parse_redis_url(require_str("LTI_STATE_REDIS_URL"))
SESSION_REDIS_URL = parse_redis_url(require_str("SESSION_REDIS_URL"))

# Named once so nothing has to spell it twice.
LTI_STATE_CACHE_ALIAS = "lti_state"
SESSION_CACHE_ALIAS = "sessions"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "KEY_PREFIX": "gau",
    },
    # OIDC state and nonces for launches in flight (task 1.4). Its own Redis
    # logical database, so clearing the page cache cannot invalidate a handshake
    # half-way through — or, worse, drop the nonce that prevents a launch being
    # replayed. Entries expire; see apps/lti/tool_conf.py for the lifetime.
    LTI_STATE_CACHE_ALIAS: {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": LTI_STATE_REDIS_URL,
        "KEY_PREFIX": "lti",
    },
    # Sessions, on a database of their own for the same reason and a sharper
    # one: a session is not cache. Sharing the page cache means that clearing a
    # stale page — a routine, low-stakes operation — signs every reader out
    # mid-chapter, and that memory pressure can evict a session under an LRU
    # policy. Neither failure announces itself as anything but "I got logged
    # out". See DECISIONS.md D-039.
    SESSION_CACHE_ALIAS: {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": SESSION_REDIS_URL,
        "KEY_PREFIX": "session",
    },
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_NAME = "gau_session"
# A Canvas launch is a working session, not a long-lived login. Task 1.9
# narrows the cookie further for the iframe context.
SESSION_COOKIE_AGE = get_int("SESSION_COOKIE_AGE", 60 * 60 * 12)
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True

# The reader runs inside a Canvas iframe, which makes every request to this
# platform a cross-site one. A cookie without SameSite=None is simply not sent,
# and browsers reject SameSite=None unless the cookie is also Secure — so these
# two travel together and belong in base, not in production settings alone.
# Getting this wrong does not fail loudly: the launch works, and then every
# subsequent request arrives anonymous.
#
# Locally this means the platform must be reached over http://localhost or
# http://127.0.0.1, which browsers treat as secure contexts, or over HTTPS.
# A LAN address will silently drop the session.
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True

# The same reasoning for CSRF, except that the frontend has to read this one to
# echo it back, so it is deliberately not HttpOnly.
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False

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

# Scheduled work. Canvas is authoritative for enrolment, but it does not tell
# us when someone leaves — only a roster read does (task 1.13). Six hours is a
# deliberate compromise: a departed student keeps access for at most that long,
# and the platform is not polling Canvas for every course every few minutes.
# A launch still reconciles the launching user immediately.
ROSTER_SYNC_INTERVAL_SECONDS = get_int("ROSTER_SYNC_INTERVAL_SECONDS", 6 * 60 * 60)

CELERY_BEAT_SCHEDULE = {
    "sync-canvas-rosters": {
        "task": "apps.lti.tasks.sync_all_rosters",
        "schedule": ROSTER_SYNC_INTERVAL_SECONDS,
    },
}

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
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
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

# Two different limits that are easy to conflate:
#
# DATA_UPLOAD_MAX_MEMORY_SIZE caps the NON-FILE part of a request body — JSON,
# form fields. It does not apply to uploaded files at all. The largest
# legitimate non-file body is a Tiptap JSON document for one section, so 10 MB
# is generous; anything larger is refused before it is read into memory.
#
# FILE_UPLOAD_MAX_MEMORY_SIZE is the point at which an uploaded file is streamed
# to disk instead of held in memory. It is not a size limit either.
#
# The ceiling on an uploaded document is client_max_body_size in
# docker/nginx/nginx.conf (64 MB). Per-type size validation for images and
# imports is owed in tasks 3.10 and 3.11.
DATA_UPLOAD_MAX_MEMORY_SIZE = get_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
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

LOGGING: dict[str, Any] = {
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

# Which Canvas platforms this tool trusts. A path to a JSON file listing the
# registrations, read by `manage.py sync_lti_platforms` and written into the
# lti_ltiplatform table. Issuers, client ids and deployment ids are deployment
# facts, never literals in code (rule C.6), and the file is deliberately not a
# settings value itself: it holds several records, changes on its own schedule,
# and belongs in a mounted file rather than a process environment.
LTI_PLATFORMS_FILE = get_str("LTI_PLATFORMS_FILE")

# Where this tool's own RSA private keys live, one PEM per key named by its
# kid. Files rather than database rows, because a database dump travels much
# more freely than a key file (DECISIONS.md D-026). Generated by
# `manage.py create_lti_key`; the public halves are published at /lti/jwks/.
LTI_TOOL_KEY_DIR = Path(get_str("LTI_TOOL_KEY_DIR") or BASE_DIR / "lti-keys")

APPEND_SLASH = True
X_FRAME_OPTIONS = "DENY"  # relaxed for the launch routes only, in task 4.4
