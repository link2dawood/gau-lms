"""Typed environment reader.

Settings come from the environment and nothing else (architecture rule C.6: no
users, courses, roles, Canvas URLs, client ids or deployment ids in code). This
module is the single place that reads it, so every setting is parsed the same
way and a missing required value fails at import time with a message naming the
variable — not at 3am with an AttributeError.

Deliberately built on the standard library: no configuration dependency is
added to the stack for work that ``os.environ`` and ``urllib.parse`` already do.
"""

from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

__all__ = [
    "ImproperlyConfigured",
    "get_bool",
    "get_int",
    "get_list",
    "get_str",
    "parse_database_url",
    "parse_redis_url",
    "require_str",
]


class ImproperlyConfigured(Exception):
    """A required environment variable is missing or cannot be parsed."""


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def get_str(name: str, default: str | None = None) -> str | None:
    """Return a variable as text, or ``default`` when unset or empty."""
    value = os.environ.get(name, "").strip()
    return value or default


def require_str(name: str) -> str:
    """Return a variable as text, or fail loudly naming the variable."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(
            f"Required environment variable {name} is not set. "
            f"See .env.example for the full list and copy it to .env."
        )
    return value


def get_bool(name: str, default: bool) -> bool:
    """Return a variable as a boolean.

    Accepts the usual spellings in either case. An unset or empty variable
    yields ``default``, matching :func:`get_str`. An unrecognised value is an
    error rather than a silent ``False`` — ``DEBUG=Ture`` must not quietly ship
    a production setting.
    """
    raw = get_str(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ImproperlyConfigured(
        f"Environment variable {name}={raw!r} is not a boolean. "
        f"Use one of: {', '.join(sorted(_TRUE | _FALSE))}."
    )


def get_int(name: str, default: int) -> int:
    """Return a variable as an integer, failing on a non-numeric value."""
    raw = get_str(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {name}={raw!r} is not an integer."
        ) from exc


def get_list(name: str, default: list[str] | None = None) -> list[str]:
    """Return a comma-separated variable as a list, discarding empty entries."""
    raw = get_str(name)
    if raw is None:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_database_url(url: str) -> dict[str, object]:
    """Turn a ``postgres://`` URL into a Django DATABASES entry.

    Only PostgreSQL is supported: the content model relies on JSONB, full-text
    search and hierarchical queries, so a SQLite fallback would let tests pass
    against a database the platform never runs on.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(
            f"DATABASE_URL must use the postgres:// scheme, got {parsed.scheme!r}. "
            f"The platform requires PostgreSQL."
        )
    name = parsed.path.lstrip("/")
    if not name:
        raise ImproperlyConfigured("DATABASE_URL does not name a database.")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        # Reuse connections between requests. Reader traffic is many small
        # queries against the same few tables; a fresh connect per request is
        # pure overhead.
        "CONN_MAX_AGE": get_int("DATABASE_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
        "ATOMIC_REQUESTS": False,
    }


def parse_redis_url(url: str) -> str:
    """Validate a Redis URL and return it unchanged."""
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss", "unix"}:
        raise ImproperlyConfigured(f"Expected a redis:// URL, got {parsed.scheme!r} in {url!r}.")
    return url
