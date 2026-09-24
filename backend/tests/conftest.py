"""Shared pytest fixtures.

Tests run against PostgreSQL, never SQLite: the content model depends on JSONB,
full-text search and hierarchical queries, so a suite that passed against SQLite
would be testing a database the platform never runs on.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    """An unauthenticated HTTP client.

    Deliberately anonymous by default. Authenticated clients are built per test
    from a Canvas launch once provisioning exists (task 1.8), so no test can
    accidentally inherit a privileged session it did not ask for.
    """
    return Client()


@pytest.fixture
def clear_cache() -> Iterator[None]:
    """Empty the cache around a test that depends on cache state."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def launch_as() -> Callable[..., Client]:
    """Build a client carrying the session a verified launch would have left.

    Opt-in, and deliberately a factory rather than a ready-made client: a test
    about cross-course refusal needs two of these, in two courses, and a test
    about roles needs to choose one. Nothing inherits a privileged session it
    did not ask for.

    It writes exactly the two session keys `establish_session` writes, taken
    from that module rather than spelled out again, so a rename there breaks
    these tests instead of silently making them test nothing.
    """
    from apps.courses.services import Course, Role
    from services.launch_session import SESSION_COURSE_KEY, SESSION_ROLE_KEY
    from tests.factories import UserFactory

    def _launch(course: Course, *, user: object | None = None, role: Role | None = None) -> Client:
        client = Client()
        client.force_login(user or UserFactory())
        session = client.session
        session[SESSION_COURSE_KEY] = str(course.pk)
        session[SESSION_ROLE_KEY] = (role or Role.STUDENT).value
        session.save()
        return client

    return _launch
