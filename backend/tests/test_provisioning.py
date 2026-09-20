"""Turning a verified launch into records.

Acceptance criterion 1 — "a Canvas user launches without creating a second
account" — and criterion 3, that the course context Canvas sent is the one
used, are asserted here.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.courses.models import Course, CourseMembership, Role
from apps.lti.services import parse_launch_claims
from services.provisioning import provision_launch
from tests.factories import INSTRUCTOR, LEARNER, UserFactory, launch_body

User = get_user_model()

pytestmark = pytest.mark.django_db


def provision(**overrides: object) -> object:
    return provision_launch(parse_launch_claims(launch_body(**overrides)))


class TestFirstLaunch:
    def test_it_creates_exactly_one_of_each(self) -> None:
        context = provision()
        assert User.objects.count() == 1
        assert Course.objects.count() == 1
        assert CourseMembership.objects.count() == 1
        assert context.role is Role.STUDENT

    def test_the_course_context_canvas_sent_is_the_one_used(self) -> None:
        """Criterion 3. The identity is the three columns of D-032."""
        course = provision().course
        assert course.canvas_course_id == "4321"
        assert course.title == "Fundamentals of Nursing"
        assert course.platform_guid != ""

    def test_the_reader_has_no_usable_password(self) -> None:
        """Canvas authenticates. A usable password would be a second way in."""
        assert provision().user.has_usable_password() is False

    def test_a_launch_never_grants_cms_access(self) -> None:
        """No Canvas role confers is_content_admin (D-023), including an
        administrator's."""
        from apps.lti.services import CLAIM_ROLES

        system_admin = "http://purl.imsglobal.org/vocab/lti/system/person#Administrator"
        context = provision(**{CLAIM_ROLES: [system_admin]})
        assert context.role is Role.ADMIN
        assert context.user.is_content_admin is False


class TestRepeatLaunch:
    def test_the_same_person_never_gets_a_second_account(self) -> None:
        """Criterion 1, enforced by the database rather than by application code."""
        first = provision()
        second = provision()
        assert first.user.pk == second.user.pk
        assert User.objects.count() == 1

    def test_launching_twice_creates_nothing_the_second_time(self) -> None:
        provision()
        provision()
        assert (User.objects.count(), Course.objects.count(), CourseMembership.objects.count()) == (
            1,
            1,
            1,
        )

    def test_a_promotion_in_canvas_takes_effect(self) -> None:
        from apps.lti.services import CLAIM_ROLES

        assert provision(**{CLAIM_ROLES: [LEARNER]}).role is Role.STUDENT
        assert provision(**{CLAIM_ROLES: [INSTRUCTOR]}).role is Role.FACULTY

    def test_a_demotion_takes_effect_just_as_promptly(self) -> None:
        """The dangerous direction. A role written once and never revised would
        leave a former teacher with the faculty view indefinitely."""
        from apps.lti.services import CLAIM_ROLES

        provision(**{CLAIM_ROLES: [INSTRUCTOR]})
        assert provision(**{CLAIM_ROLES: [LEARNER]}).role is Role.STUDENT

    def test_a_name_canvas_stops_sending_is_not_forgotten(self) -> None:
        """Course privacy settings differ, so the same person arrives with a
        name from one course and without it from another. Blanking it would
        make someone's name depend on where they last launched from."""
        provision(name="A Student")
        context = provision(name="", email="")
        assert context.user.name == "A Student"
        assert context.user.email == "student@gau.edu.tr"

    def test_a_returning_member_is_reactivated_not_recreated(self) -> None:
        """Their reading position hangs from this row (task 2.9)."""
        membership = provision().membership
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        again = provision().membership
        assert again.pk == membership.pk
        assert again.is_active is True
        assert CourseMembership.objects.count() == 1


class TestSeparateCourses:
    def test_two_courses_on_one_canvas_stay_separate(self) -> None:
        from apps.lti.services import CLAIM_CONTEXT

        provision()
        provision(**{CLAIM_CONTEXT: {"id": "9999", "title": "Anatomy", "label": "ANAT-101"}})
        assert Course.objects.count() == 2
        assert User.objects.count() == 1
        assert CourseMembership.objects.count() == 2

    def test_two_canvases_sharing_an_issuer_do_not_merge(self) -> None:
        """Every Instructure-hosted Canvas presents the same `iss`, so without
        the platform guid one university's course 4321 and another's would land
        on one row — merging two rosters (D-032)."""
        from apps.lti.services import CLAIM_TOOL_PLATFORM

        provision()
        provision(**{CLAIM_TOOL_PLATFORM: {"guid": "other.instructure.com"}})
        assert Course.objects.count() == 2


@pytest.mark.django_db
def test_an_existing_account_is_reused_rather_than_duplicated() -> None:
    """The account already exists — from an earlier course, say. Provisioning
    must find it, not collide with it."""
    existing = UserFactory(canvas_user_id="535fa085-1a81-4c07-bb56-b0d4ae1c8e1c")
    assert provision().user.pk == existing.pk
    assert User.objects.count() == 1
