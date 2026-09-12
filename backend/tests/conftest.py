"""Shared pytest fixtures.

Tests run against PostgreSQL, never SQLite: the content model depends on JSONB,
full-text search and hierarchical queries, so a suite that passed against SQLite
would be testing a database the platform never runs on.
"""

from __future__ import annotations

from collections.abc import Iterator

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
