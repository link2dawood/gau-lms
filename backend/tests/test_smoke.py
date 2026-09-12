"""Smoke tests for the project skeleton.

These assert behaviour the whole platform rests on: that the application boots
with the intended configuration, that the readiness endpoint tells the truth,
and that the API denies by default. They are deliberately few — the point is to
prove the harness runs and the foundations hold, not to pre-empt later tasks.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse


class TestReadiness:
    """The readiness endpoint is what a load balancer and the uptime monitor read."""

    @pytest.mark.django_db
    def test_reports_ok_when_dependencies_are_reachable(self, client: Client) -> None:
        response = client.get(reverse("health"))

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["cache"] == "ok"

    def test_liveness_does_not_touch_the_database(self, client: Client) -> None:
        """No django_db marker: this must pass without database access at all.

        Liveness and readiness are separate so a restart policy cannot kill a
        healthy application process because PostgreSQL is briefly unavailable.
        """
        response = client.get(reverse("liveness"))

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.django_db
    def test_accepts_head_as_well_as_get(self, client: Client) -> None:
        """Several uptime monitors send HEAD; rejecting it reports a false outage."""
        assert client.head(reverse("health")).status_code == 200

    @pytest.mark.django_db
    def test_rejects_methods_that_are_not_reads(self, client: Client) -> None:
        for method in (client.post, client.put, client.delete):
            assert method(reverse("health")).status_code in (403, 405)

    @pytest.mark.django_db
    def test_response_is_not_cacheable(self, client: Client) -> None:
        """A cached readiness response would report a dead platform as healthy."""
        cache_control = client.get(reverse("health"))["Cache-Control"]

        assert "no-store" in cache_control
        assert "no-cache" in cache_control


class TestConfiguration:
    """Settings that are load-bearing for security, asserted rather than assumed."""

    def test_api_denies_by_default(self) -> None:
        """A view that forgets its permission class must fail closed (D-012)."""
        assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
            "rest_framework.permissions.IsAuthenticated"
        ]

    def test_database_is_postgresql(self) -> None:
        assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"

    def test_original_scheme_is_read_from_the_proxy(self) -> None:
        """Nginx terminates TLS; without this Django cannot issue Secure cookies,
        which a Canvas iframe launch requires (task 1.9)."""
        assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")

    def test_no_custom_user_model_is_declared_yet(self) -> None:
        """Guards D-009.

        AUTH_USER_MODEL and apps.accounts.User must land together in task 1.1.
        If this test fails because the setting appeared without the app, the
        project will not boot; if it fails because 1.1 has landed, delete it.
        """
        assert settings.AUTH_USER_MODEL == "auth.User"
        assert "apps.accounts" not in settings.INSTALLED_APPS
