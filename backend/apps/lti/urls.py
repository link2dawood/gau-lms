"""Routes owned by the LTI module, mounted at /lti/ by core/urls.py."""

from __future__ import annotations

from django.urls import path

from apps.lti import views

app_name = "lti"

urlpatterns = [
    path("jwks/", views.jwks, name="jwks"),
    path("login/", views.login, name="login"),
    path("launch/", views.launch, name="launch"),
    path("session/", views.session, name="session"),
    path("context/", views.LaunchContextView.as_view(), name="context"),
]
