"""Course scoping, enforced as a permission.

The twelfth acceptance criterion is that a user cannot reach another course's
content. That is enforced here rather than in each view, because a check that
every view has to remember is a check that one view will eventually forget.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.courses.services import Course
from apps.lti.middleware import launch_scope

__all__ = ["CourseScoped"]


class CourseScoped(BasePermission):
    """Requires a launch scope, and confines objects to that course.

    `has_permission` establishes that the request came through a Canvas launch
    at all. `has_object_permission` is what actually stops one course reading
    another's content, so it must be reached — a view that returns a queryset
    without calling `check_object_permissions` has to filter by the scope
    itself.
    """

    message = "This content belongs to a different course."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return launch_scope(request) is not None

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        scope = launch_scope(request)
        if scope is None:
            return False

        course_id = _course_id_of(obj)
        # Fails closed. An object this permission cannot place in a course is
        # not one it can vouch for, and guessing would defeat the point.
        return course_id is not None and course_id == scope.course_id


def _course_id_of(obj: Any) -> str | None:
    """Which course an object belongs to, if it can be determined.

    Two shapes only: a Course itself, and anything carrying a `course_id` —
    which every Django model with a `course` foreign key does, including one
    whose relation is deferred. A model with neither must not be guarded by
    this permission; it would be denied every time, which is the right way
    round to be wrong.

    The Course case is an `isinstance`, not a check on the class name. A name
    comparison happens to be correct while exactly one class is called Course,
    and stops being correct silently.
    """
    if isinstance(obj, Course):
        return str(obj.pk)

    course_id = getattr(obj, "course_id", None)
    return str(course_id) if course_id is not None else None
