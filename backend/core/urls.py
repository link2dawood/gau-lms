"""Root URL configuration.

Ownership of the URL space is split at the edge by Nginx
(docker/nginx/conf.d/app.conf): Django serves ``/api/``, ``/lti/`` and
``/admin/``; everything else belongs to the Next.js frontend.

Each module mounts its own routes here as its task lands, so this file stays a
map of the platform rather than a place where views are defined.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from core.health import health, liveness

urlpatterns = [
    # Operational. Unauthenticated by design; see core/health.py.
    path("api/health/", health, name="health"),
    path("api/live/", liveness, name="liveness"),
    path("admin/", admin.site.urls),
    # JWKS and OIDC login; the launch endpoint joins them in task 1.5.
    path("lti/", include("apps.lti.urls")),
    # Still to be mounted, each by the task that builds it: the content API at
    # /api/ (2.6), reading positions (2.10), search (2.13), and the CMS API at
    # /api/cms/ (3.2).
]
