"""Turning a verified launch into a signed-in session.

Two ways in, because one of them does not always work.

The **cookie** path is the normal one: the launch response sets a session
cookie marked ``SameSite=None; Secure; HttpOnly`` and the browser sends it back
on subsequent requests from inside the Canvas iframe.

The **ticket** path exists because a browser that blocks third-party cookies
will silently discard that cookie. The launch therefore also mints a
short-lived, single-use ticket and hands it to the frontend, which can redeem
it for a session from a context where cookies do work — the new window that
task 1.10 opens.

Tickets live in the LTI Redis database with the OIDC state and nonces, kept
apart from the page cache for the same reason (D-008).
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import login as django_login
from django.core.cache import caches
from django.http import HttpRequest

from apps.accounts.services import User, get_user
from apps.courses.services import Role
from services.provisioning import LaunchContext

logger = logging.getLogger(__name__)

__all__ = [
    "SESSION_COURSE_KEY",
    "SESSION_ROLE_KEY",
    "LaunchTicket",
    "RedeemedSession",
    "establish_session",
    "redeem_launch_ticket",
]

# Where the launch context lives on the session. Task 1.11's course-scope
# middleware reads these, so they are named once here rather than spelled out
# at each use.
SESSION_COURSE_KEY = "lti_course_id"
SESSION_ROLE_KEY = "lti_role"

_TICKET_PREFIX = "launch-ticket:"

# Long enough for a redirect and a page load, short enough that a ticket
# leaking through browser history or a Referer header is worth little. It is
# single use as well: redeeming it deletes it.
TICKET_TTL_SECONDS = 120

# The user has no usable password, so there is nothing for `authenticate()` to
# check — Canvas has already done the authenticating and PyLTI1p3 has verified
# it. `login()` needs a backend named explicitly in that case.
_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


@dataclass(frozen=True)
class LaunchTicket:
    token: str
    expires_in: int


@dataclass(frozen=True)
class RedeemedSession:
    """What a redeemed ticket established.

    Carries the ids the ticket held rather than re-reading the course and
    membership: the caller only needs to know which course the session is now
    scoped to, and two extra queries on the critical path of a launch buy
    nothing.
    """

    user: User
    course_id: str
    role: Role


def establish_session(request: HttpRequest, context: LaunchContext) -> LaunchTicket:
    """Sign the launching user in and mint a ticket for the frontend.

    `django_login` rotates the session key, so a session identifier an attacker
    managed to plant before the launch cannot survive it.
    """
    django_login(request, context.user, backend=_AUTH_BACKEND)
    request.session[SESSION_COURSE_KEY] = str(context.course.pk)
    request.session[SESSION_ROLE_KEY] = context.role.value

    return _mint_ticket(context)


def redeem_launch_ticket(request: HttpRequest, token: str) -> RedeemedSession | None:
    """Exchange a ticket for a session, once.

    Returns None for anything that is not a live ticket — unknown, already
    used, expired, or naming an account that has since been deactivated. The
    caller reports all of those the same way: a ticket that distinguishes
    "expired" from "never existed" tells an attacker which guesses were close.
    """
    payload = _consume(token)
    if payload is None:
        return None

    user = get_user(str(payload.get("user_id", "")))
    if user is None:
        logger.warning("Launch ticket named a user who is gone or deactivated.")
        return None

    course_id = str(payload.get("course_id", ""))
    role = _role_from(payload.get("role"))
    if not course_id:
        logger.warning("Launch ticket carried no course; refusing to establish a session.")
        return None

    django_login(request, user, backend=_AUTH_BACKEND)
    request.session[SESSION_COURSE_KEY] = course_id
    request.session[SESSION_ROLE_KEY] = role.value
    return RedeemedSession(user=user, course_id=course_id, role=role)


def _role_from(value: object) -> Role:
    """A ticket's role, or the least privileged one if it is not recognised."""
    try:
        return Role(value)
    except ValueError:
        logger.warning("Launch ticket carried an unknown role %r; treating as student.", value)
        return Role.STUDENT


def _mint_ticket(context: LaunchContext) -> LaunchTicket:
    token = secrets.token_urlsafe(32)
    caches[settings.LTI_STATE_CACHE_ALIAS].set(
        f"{_TICKET_PREFIX}{token}",
        {
            "user_id": str(context.user.pk),
            "course_id": str(context.course.pk),
            "role": context.role.value,
        },
        TICKET_TTL_SECONDS,
    )
    return LaunchTicket(token=token, expires_in=TICKET_TTL_SECONDS)


def _consume(token: str) -> dict[str, Any] | None:
    """Read a ticket, and let the delete decide who gets it.

    Both halves matter. The read supplies the payload; the delete decides
    whether this caller is the one allowed to use it. Redis reports how many
    keys `DEL` removed, so of two simultaneous redemptions exactly one sees a
    truthy result and the other is refused — the read racing is harmless
    because the delete does not. Same reasoning as the single-use nonce in
    apps/lti/tool_conf.py.
    """
    if not token:
        return None
    cache = caches[settings.LTI_STATE_CACHE_ALIAS]
    key = f"{_TICKET_PREFIX}{token}"
    payload = cache.get(key)
    if payload is None or not cache.delete(key):
        return None
    return payload if isinstance(payload, dict) else None
