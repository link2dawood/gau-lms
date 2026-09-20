"""Celery application.

Slow work never runs inside a request (architecture rule C.10): document
imports, search indexing and Canvas roster synchronisation are tasks.

Queues are separated by cost so a 338-page PDF import cannot delay a search
reindex triggered by an administrator hitting Publish:

    imports   long-running document conversion (task 3.11)
    indexing  Meilisearch synchronisation (task 2.12)
    canvas    Names and Roles roster sync (task 1.13)
    default   everything else
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")

app = Celery("gau_textbook")

# All Celery settings live in Django settings under a CELERY_ prefix, so there
# is one place configuration comes from.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Each app module's tasks.py is discovered automatically once the app is added
# to INSTALLED_APPS.
app.autodiscover_tasks()

app.conf.task_default_queue = "default"
app.conf.task_routes = {
    "apps.imports.tasks.*": {"queue": "imports"},
    "apps.search.tasks.*": {"queue": "indexing"},
    "apps.lti.tasks.*": {"queue": "canvas"},
}
