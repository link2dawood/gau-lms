"""Root URL configuration.

Ownership of the URL space is split at the edge by Nginx
(docker/nginx/conf.d/app.conf): Django serves ``/api/``, ``/lti/`` and
``/admin/``; everything else belongs to the Next.js frontend.

Each module mounts its own routes here as its task lands, so this file stays a
map of the platform rather than a place where views are defined.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import path

from config.health import health, liveness

urlpatterns = [
    # Operational. Unauthenticated by design; see config/health.py.
    path("api/health/", health, name="health"),
    path("api/live/", liveness, name="liveness"),

    path("admin/", admin.site.urls),

    # Mounted by their tasks:
    #   path("lti/", include("apps.lti.urls")),           task 1.3
    #   path("api/", include("apps.content.urls")),       task 2.6
    #   path("api/", include("apps.reader.urls")),        task 2.10
    #   path("api/", include("apps.search.urls")),        task 2.13
    #   path("api/cms/", include("apps.cms.urls")),       task 3.2
]
