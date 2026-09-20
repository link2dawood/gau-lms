"""Test settings.

Built on development settings so tests exercise the same database engine and
search backend the platform actually runs on. The only changes are the ones
that make a suite fast and deterministic.
"""

from __future__ import annotations

from core.settings.dev import *

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
# Every alias the application asks for must exist here too. A missing one does
# not fail as a configuration error at startup — it raises the first time a
# test touches that cache, which reads as a broken test rather than broken
# settings.
CACHES = {
    alias: {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"gau-test-{alias}",
    }
    for alias in ("default", LTI_STATE_CACHE_ALIAS, SESSION_CACHE_ALIAS)
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

LOGGING["root"]["level"] = "WARNING"
