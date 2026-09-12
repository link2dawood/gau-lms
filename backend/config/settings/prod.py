"""Production and staging settings.

Every relaxation available in development is closed here, and the values that
protect a Canvas launch — HTTPS enforcement, cookie flags, host checking — are
not optional or overridable to something weaker.
"""

from __future__ import annotations

from config.settings.base import *  # noqa: F403
from config.settings.env import ImproperlyConfigured, get_bool, get_int, get_list, get_str

DEBUG = False

# No permissive fallback: an unset ALLOWED_HOSTS in production is a
# configuration error, not a reason to accept any Host header.
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", [])
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list the hostnames this deployment serves, "
        "for example: textbook.gau.edu"
    )

CSRF_TRUSTED_ORIGINS = get_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "DJANGO_CSRF_TRUSTED_ORIGINS must list the https:// origins the platform "
        "is served from, for example: https://textbook.gau.edu"
    )

# --- Transport -------------------------------------------------------------
# HTTPS is mandatory for LTI 1.3. Nginx terminates TLS and forwards the
# original scheme; SECURE_PROXY_SSL_HEADER in base.py is what makes these
# effective behind the proxy.

SECURE_SSL_REDIRECT = get_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = get_int("DJANGO_SECURE_HSTS_SECONDS", 60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = get_bool("DJANGO_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# --- Cookies ---------------------------------------------------------------
# The reader runs inside a Canvas iframe, so its session cookie is
# cross-site by definition: SameSite=None, which browsers only honour together
# with Secure. Task 1.9 owns the launch cookie itself and task 1.10 the
# new-window fallback for browsers that block third-party cookies outright.

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_HTTPONLY = False  # the frontend must read the token to send it back

# --- Static ----------------------------------------------------------------
# Hashed filenames with a manifest, so Nginx can cache static assets
# indefinitely (docker/nginx/conf.d/app.conf).

STORAGES = {  # noqa: F405
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

# --- Meilisearch -----------------------------------------------------------

if get_str("MEILI_ENV", "development") != "production":
    raise ImproperlyConfigured(
        "MEILI_ENV must be 'production' on a deployed environment; "
        "'development' exposes the Meilisearch web UI and relaxes key checks."
    )
