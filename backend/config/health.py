"""Readiness endpoint.

Reports whether the process can actually reach the things it needs, rather than
merely whether it is running. Consumed by the container healthcheck, by Nginx
during a deployment, and by the uptime monitor on the server (task 4.8).

This is the one route on the platform that is deliberately unauthenticated: a
load balancer cannot present a Canvas session. It therefore reveals nothing
beyond reachability — no versions, no hostnames, no configuration, and no error
detail from the underlying exception.
"""

from __future__ import annotations

import logging
from typing import Literal

from django.core.cache import cache
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

Status = Literal["ok", "error"]

_PROBE_KEY = "healthcheck:probe"


def _check_database() -> Status:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check: database unreachable")
        return "error"
    return "ok"


def _check_cache() -> Status:
    try:
        cache.set(_PROBE_KEY, "1", timeout=10)
        if cache.get(_PROBE_KEY) != "1":
            logger.error("Health check: cache did not return the value written")
            return "error"
    except Exception:
        logger.exception("Health check: cache unreachable")
        return "error"
    return "ok"


@require_http_methods(["GET", "HEAD"])
@never_cache
def health(request: HttpRequest) -> JsonResponse:
    """Return 200 when every dependency responds, 503 otherwise."""
    checks: dict[str, Status] = {
        "database": _check_database(),
        "cache": _check_cache(),
    }
    healthy = all(status == "ok" for status in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "error", "checks": checks},
        status=200 if healthy else 503,
    )


@require_http_methods(["GET", "HEAD"])
@never_cache
def liveness(request: HttpRequest) -> JsonResponse:
    """Return 200 if the process is serving, without touching a dependency.

    Kept separate from readiness so a restart policy cannot kill a healthy
    application process because PostgreSQL is briefly unavailable.
    """
    return JsonResponse({"status": "ok"})
