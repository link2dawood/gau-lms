"""Course scoping — acceptance criterion 12.

A user must never reach another course's content. The scope comes from the
session, which only a verified launch writes; a course id in a request is a
question, not an answer.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.courses.models import Role
from apps.lti.middleware import SCOPE_ATTR, CourseScopeMiddleware, LaunchScope, launch_scope
from apps.lti.permissions import CourseScoped
from services.launch_session import SESSION_COURSE_KEY, SESSION_ROLE_KEY
from tests.factories import CourseFactory, CourseMembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def request_with_session(user: object, **session: str) -> object:
    request = RequestFactory().get("/")
    request.user = user  # type: ignore[attr-defined]
    request.session = session  # type: ignore[attr-defined]
    CourseScopeMiddleware(lambda _req: None)(request)  # type: ignore[arg-type,return-value]
    return request


class TestTheMiddlewareDecidesWhoHasAScope:
    def test_an_anonymous_request_has_none(self) -> None:
        request = request_with_session(AnonymousUser(), **{SESSION_COURSE_KEY: "any"})
        assert launch_scope(request) is None  # type: ignore[arg-type]

    def test_a_django_admin_login_has_none(self) -> None:
        """An operator signed in at /admin/ is authenticated and has never
        launched. It is the course key that gates a scope, not the user."""
        request = request_with_session(UserFactory())
        assert launch_scope(request) is None  # type: ignore[arg-type]

    def test_a_launched_session_has_one(self) -> None:
        course = CourseFactory()
        request = request_with_session(
            UserFactory(),
            **{SESSION_COURSE_KEY: str(course.pk), SESSION_ROLE_KEY: Role.FACULTY.value},
        )
        scope = launch_scope(request)  # type: ignore[arg-type]
        assert scope is not None
        assert scope.course_id == str(course.pk)
        assert scope.role is Role.FACULTY

    def test_an_unreadable_role_degrades_to_the_least_privilege(self) -> None:
        """A session from an older release, or a tampered one, must not escalate
        and must not raise."""
        course = CourseFactory()
        request = request_with_session(
            UserFactory(),
            **{SESSION_COURSE_KEY: str(course.pk), SESSION_ROLE_KEY: "SUPERUSER"},
        )
        scope = launch_scope(request)  # type: ignore[arg-type]
        assert scope is not None
        assert scope.role is Role.STUDENT

    def test_the_scope_attribute_cannot_be_pre_seeded(self) -> None:
        """The middleware overwrites it on every request, before any view runs."""
        request = RequestFactory().get("/")
        setattr(request, SCOPE_ATTR, LaunchScope(course_id="smuggled", role=Role.ADMIN))
        request.user = AnonymousUser()  # type: ignore[attr-defined]
        request.session = {}  # type: ignore[attr-defined]
        CourseScopeMiddleware(lambda _req: None)(request)  # type: ignore[arg-type,return-value]
        assert launch_scope(request) is None


class TestCrossCourseAccessIsRefused:
    def _request(self, course_id: str) -> object:
        request = RequestFactory().get("/")
        setattr(request, SCOPE_ATTR, LaunchScope(course_id=course_id, role=Role.STUDENT))
        return request

    def test_an_object_from_the_launched_course_is_allowed(self) -> None:
        course = CourseFactory()
        membership = CourseMembershipFactory(course=course)
        request = self._request(str(course.pk))
        assert CourseScoped().has_object_permission(request, None, membership) is True  # type: ignore[arg-type]

    def test_an_object_from_another_course_is_refused(self) -> None:
        """Criterion 12."""
        launched, other = CourseFactory(), CourseFactory()
        membership = CourseMembershipFactory(course=other)
        request = self._request(str(launched.pk))
        assert CourseScoped().has_object_permission(request, None, membership) is False  # type: ignore[arg-type]

    def test_the_course_itself_is_placed_correctly(self) -> None:
        launched, other = CourseFactory(), CourseFactory()
        request = self._request(str(launched.pk))
        assert CourseScoped().has_object_permission(request, None, launched) is True  # type: ignore[arg-type]
        assert CourseScoped().has_object_permission(request, None, other) is False  # type: ignore[arg-type]

    def test_an_object_with_no_course_is_refused_rather_than_guessed(self) -> None:
        request = self._request(str(CourseFactory().pk))
        for obj in (object(), "a-string", None, UserFactory()):
            assert CourseScoped().has_object_permission(request, None, obj) is False  # type: ignore[arg-type]

    def test_without_a_scope_nothing_is_permitted(self) -> None:
        request = RequestFactory().get("/")
        assert CourseScoped().has_permission(request, None) is False  # type: ignore[arg-type]


class TestTheLaunchContextEndpoint:
    def test_it_refuses_a_session_that_never_launched(self, client: Client) -> None:
        client.force_login(UserFactory())
        assert client.get(reverse("lti:context")).status_code == 403

    def test_it_refuses_an_anonymous_request(self, client: Client) -> None:
        assert client.get(reverse("lti:context")).status_code in (401, 403)

    def test_it_reports_the_launched_course_and_nothing_else(self, client: Client) -> None:
        user, course = UserFactory(), CourseFactory()
        client.force_login(user)
        session = client.session
        session[SESSION_COURSE_KEY] = str(course.pk)
        session[SESSION_ROLE_KEY] = Role.FACULTY.value
        session.save()

        payload = client.get(reverse("lti:context")).json()
        assert payload["course"]["id"] == str(course.pk)
        assert payload["role"] == Role.FACULTY.value
        assert payload["user"]["name"] == user.name
