"""Carrying the launch's course context on every request.

A launch establishes which course the reader is in. Every request after it must
be answered in that context and no other — architecture rule C.8, and the
twelfth acceptance criterion. Putting that on the request once, here, means no
view has to remember to read it out of the session, and a view that forgets to
*check* it is caught by the permission class rather than quietly serving
another course's content.

The scope is read from the session rather than from anything the client sends.
A course id in a URL is a request; a course id in the session is a fact
established by a signed Canvas launch.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse
from rest_framework.request import Request

from apps.courses.services import Role
from services.launch_session import SESSION_COURSE_KEY, SESSION_ROLE_KEY

__all__ = ["CourseScopeMiddleware", "LaunchScope", "launch_scope"]

# Attached with setattr and read with getattr rather than declared on the
# request: HttpRequest has no such field, and inventing one would mean a type
# ignore at every use instead of the two here.
SCOPE_ATTR = "lti_launch_scope"


@dataclass(frozen=True)
class LaunchScope:
    """The course and standing a request inherits from its launch."""

    course_id: str
    role: Role


def launch_scope(request: HttpRequest | Request) -> LaunchScope | None:
    """The launch scope for this request, or None if it has none.

    None means the request did not arrive through a Canvas launch. It is never
    a reason to fall back to something permissive.
    """
    scope = getattr(request, SCOPE_ATTR, None)
    return scope if isinstance(scope, LaunchScope) else None


class CourseScopeMiddleware:
    """Reads the launch context out of the session onto the request.

    Must sit after `AuthenticationMiddleware`: a scope without an authenticated
    user is meaningless, and treating one as valid would hand a course context
    to an anonymous request.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        setattr(request, SCOPE_ATTR, _scope_from_session(request))
        return self.get_response(request)


def _scope_from_session(request: HttpRequest) -> LaunchScope | None:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None

    course_id = request.session.get(SESSION_COURSE_KEY, "")
    if not course_id:
        return None

    try:
        role = Role(request.session.get(SESSION_ROLE_KEY, ""))
    except ValueError:
        # A session written by an older release, or tampered with. The least
        # privileged reading is the only safe one.
        role = Role.STUDENT

    return LaunchScope(course_id=str(course_id), role=role)
