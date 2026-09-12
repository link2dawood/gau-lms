"""Test settings.

Built on development settings so tests exercise the same database engine and
search backend the platform actually runs on. The only changes are the ones
that make a suite fast and deterministic.
"""

from __future__ import annotations

from config.settings.dev import *

DEBUG = False

# Password hashing dominates the runtime of any suite that creates users.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Tasks run in-process so a test can assert on their result directly. The
# production path is still exercised: task code is unchanged, only the
# transport is bypassed.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# In-memory cache, so one test cannot see another's keys and a developer's
# running stack is untouched by the suite.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "gau-test",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

LOGGING["root"]["level"] = "WARNING"
