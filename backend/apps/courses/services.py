"""Public interface of the courses module.

Other modules reach courses through this file and never import
``apps.courses.models`` directly (architecture rule C.1). It owns the
translation from Canvas's vocabulary into this platform's, and the upserts a
launch performs. Orchestrating those upserts with the accounts module is
``services/provisioning.py``, because it belongs to no single module.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.content.services import Book
from apps.courses.models import Course, CourseBook, CourseMembership, Role
from utils.db import create_or_reread

logger = logging.getLogger(__name__)

__all__ = [
    "Course",
    "CourseBook",
    "CourseMembership",
    "Role",
    "active_book_link",
    "courses_with_roster_service",
    "deactivate_memberships_absent_from",
    "find_course",
    "get_course",
    "link_course_to_book",
    "mark_roster_synced",
    "normalise_role",
    "upsert_course",
    "upsert_membership",
]

# The IMS LIS and LTI role vocabularies. These are specification constants,
# identical on every LTI 1.3 platform, in the same way the claim URIs in
# apps/lti/views.py are — not this institution's configuration, so rule C.6
# does not apply. What is deliberately NOT configurable is the mapping below:
# a deployment that could redefine which Canvas role becomes an administrator
# would be a privilege escalation waiting to be misconfigured.
_MEMBERSHIP = "http://purl.imsglobal.org/vocab/lis/v2/membership"
_INSTITUTION = "http://purl.imsglobal.org/vocab/lis/v2/institution/person"
_SYSTEM = "http://purl.imsglobal.org/vocab/lti/system/person"

# The specification allows a context role to appear as a bare term as well as a
# full URI, so both spellings are listed. Anything absent from this table is
# unrecognised and contributes nothing.
ROLE_BY_CLAIM: dict[str, Role] = {
    # Administrators of the system, the institution or the course.
    f"{_SYSTEM}#Administrator": Role.ADMIN,
    f"{_SYSTEM}#SysAdmin": Role.ADMIN,
    f"{_INSTITUTION}#Administrator": Role.ADMIN,
    f"{_MEMBERSHIP}#Administrator": Role.ADMIN,
    "Administrator": Role.ADMIN,
    # People who teach or build the course. A teaching assistant and a course
    # designer are treated as faculty: both legitimately need the faculty view
    # of a textbook, and neither is granted CMS access by it — that is
    # is_content_admin, which no Canvas role confers (D-023).
    f"{_MEMBERSHIP}#Instructor": Role.FACULTY,
    f"{_MEMBERSHIP}#ContentDeveloper": Role.FACULTY,
    f"{_MEMBERSHIP}/Instructor#TeachingAssistant": Role.FACULTY,
    f"{_INSTITUTION}#Instructor": Role.FACULTY,
    f"{_INSTITUTION}#Faculty": Role.FACULTY,
    "Instructor": Role.FACULTY,
    "ContentDeveloper": Role.FACULTY,
    "TeachingAssistant": Role.FACULTY,
    # Readers. Mentor is Canvas's observer — someone following a student's
    # progress, such as a parent. Listed explicitly at the lowest level so that
    # nobody later mistakes it for a teaching role on the strength of the name.
    f"{_MEMBERSHIP}#Learner": Role.STUDENT,
    f"{_MEMBERSHIP}#Member": Role.STUDENT,
    f"{_MEMBERSHIP}#Mentor": Role.STUDENT,
    # `Staff` in the institution vocabulary is a non-academic employee — a
    # registrar, IT, administration. Not someone who teaches, so not FACULTY:
    # otherwise anyone the institution employs gets the faculty view of every
    # course they open.
    f"{_INSTITUTION}#Staff": Role.STUDENT,
    f"{_INSTITUTION}#Student": Role.STUDENT,
    f"{_INSTITUTION}#Learner": Role.STUDENT,
    "Learner": Role.STUDENT,
    "Member": Role.STUDENT,
    "Mentor": Role.STUDENT,
}

# Ordering used to resolve someone who holds several roles at once. Canvas
# permits a teacher to also be enrolled as a student; the teaching role is the
# useful one, so the most privileged recognised role wins.
_PRECEDENCE: dict[Role, int] = {Role.STUDENT: 0, Role.FACULTY: 1, Role.ADMIN: 2}


def normalise_role(role_claims: Iterable[str] | None) -> Role:
    """Map the LTI roles claim onto this platform's three roles.

    Fails closed in every direction that could go wrong: a missing claim, an
    empty list, a list of roles this platform has never heard of, or a value
    that is not even a string all yield STUDENT, the least privileged role. An
    unrecognised role can therefore never grant more than a reader has.
    """
    resolved = Role.STUDENT
    unrecognised: list[str] = []

    for claim in role_claims or ():
        if not isinstance(claim, str):
            continue
        term = claim.strip()
        role = ROLE_BY_CLAIM.get(term)
        if role is None:
            unrecognised.append(term)
        elif _PRECEDENCE[role] > _PRECEDENCE[resolved]:
            resolved = role

    if unrecognised:
        # Not a failure — the vocabulary is extensible and platforms add to it.
        # Logged because a Canvas sending a role this table does not know is
        # how a teacher silently ends up with the student view, and the log
        # line is what turns that into a five-minute fix.
        logger.info(
            "Unrecognised LTI roles ignored, resolved as %s: %s",
            resolved,
            ", ".join(sorted(unrecognised)),
        )

    return resolved


def upsert_course(
    *,
    issuer: str,
    platform_guid: str,
    canvas_course_id: str,
    title: str = "",
    label: str = "",
    deployment_id: str = "",
    nrps_url: str = "",
) -> Course:
    """Find or create the course a launch came from.

    Identity is the three columns of D-032. The remaining fields are Canvas's
    to change and are refreshed on every launch — except that a value Canvas
    has stopped sending never blanks one it sent before, since course privacy
    settings decide what arrives.
    """
    if not canvas_course_id:
        raise ValueError("A launch with no context id cannot identify a course.")

    identity = {
        "issuer": issuer,
        "platform_guid": platform_guid,
        "canvas_course_id": canvas_course_id,
    }
    supplied = {
        "title": title,
        "label": label,
        "canvas_deployment_id": deployment_id,
        "nrps_context_memberships_url": nrps_url,
    }

    course = Course.objects.filter(**identity).first()
    if course is None:
        return create_or_reread(
            create=lambda: Course.objects.create(**identity, **supplied),
            reread=lambda: Course.objects.get(**identity),
        )

    changed = [
        field for field, value in supplied.items() if value and getattr(course, field) != value
    ]
    if changed:
        for field in changed:
            setattr(course, field, supplied[field])
        course.save(update_fields=[*changed, "updated_at"])

    return course


def upsert_membership(*, course: Course, user: AbstractBaseUser, role: Role) -> CourseMembership:
    """Record that this person is in this course, with this role.

    A membership is never deleted, so someone who left the course and returned
    is reactivated rather than recreated — which is what keeps their reading
    position attached (Section H).
    """
    membership = CourseMembership.objects.filter(course=course, user=user).first()
    if membership is None:
        return create_or_reread(
            create=lambda: CourseMembership.objects.create(course=course, user=user, role=role),
            reread=lambda: CourseMembership.objects.get(course=course, user=user),
        )

    changed = []
    if membership.role != role:
        # Canvas is authoritative, in both directions: a demotion must take
        # effect as promptly as a promotion.
        membership.role = role
        changed.append("role")
    if not membership.is_active:
        membership.is_active = True
        changed.append("is_active")
    if changed:
        membership.save(update_fields=[*changed, "updated_at"])

    return membership


def find_course(*, issuer: str, platform_guid: str, canvas_course_id: str) -> Course | None:
    """Look a course up by its Canvas identity without creating it.

    The same three columns `upsert_course` keys on (D-032), but read-only. It
    exists for callers that want to know whether a course is already known —
    answering a deep linking request, for instance — where creating one as a
    side effect of a question would be wrong.
    """
    if not canvas_course_id:
        return None
    return Course.objects.filter(
        issuer=issuer, platform_guid=platform_guid, canvas_course_id=canvas_course_id
    ).first()


def get_course(course_id: str) -> Course | None:
    """Look a course up by internal id, or None.

    Tolerates an id that is not a uuid at all. The id reaching here comes from
    a session this platform wrote, but a stale or tampered session must produce
    "no such course" rather than a 500.
    """
    try:
        return Course.objects.filter(pk=course_id).first()
    except (ValidationError, ValueError):
        return None


def courses_with_roster_service() -> list[Course]:
    """Courses Canvas will let us read a roster for.

    A course with no Names and Roles URL has never been launched from a
    platform offering the service. It is skipped rather than treated as an
    empty roster, because the two are indistinguishable from here and one of
    them would deactivate everybody.
    """
    return list(Course.objects.exclude(nrps_context_memberships_url=""))


def deactivate_memberships_absent_from(course: Course, present_user_ids: set[str]) -> int:
    """Mark everyone not on the roster inactive, and return how many.

    Never deletes. A reading position hangs from a membership, so removing the
    row would take a student's history with it (Section H). Someone who
    re-enrols is reactivated by `upsert_membership`, keeping everything they
    had.
    """
    stale = CourseMembership.objects.filter(course=course, is_active=True).exclude(
        user_id__in=present_user_ids
    )
    return stale.update(is_active=False, updated_at=timezone.now())


def mark_roster_synced(course: Course) -> None:
    course.roster_synced_at = timezone.now()
    course.save(update_fields=["roster_synced_at", "updated_at"])


def active_book_link(course: Course) -> CourseBook | None:
    """The mapping naming the textbook this course currently opens, or None.

    None means no book has been linked. It does **not** mean the book cannot be
    read — that is the content module's publication gate, applied together with
    this in ``services/course_books.py`` (D-053, D-033). Callers wanting the
    answer to "may this launch read a textbook" want that function, not this
    one.
    """
    return CourseBook.objects.filter(course=course, is_active=True).select_related("book").first()


@transaction.atomic
def link_course_to_book(course: Course, book: Book) -> CourseBook:
    """Point a course at a textbook, replacing whatever it pointed at before.

    **Deactivate first, then activate.** A partial unique index cannot be
    `DEFERRABLE` in PostgreSQL — the same limitation D-054 hit with sibling
    positions and D-056 with published versions — so activating the new mapping
    while the old one is still active violates `one_active_book_per_course`
    halfway through the transaction. The order here is the whole reason this
    function exists rather than being left to each caller to rediscover.

    Idempotent, and reversible without accumulating rows: re-linking a course to
    a textbook it used before reactivates that mapping rather than creating a
    second one saying the same thing.
    """
    CourseBook.objects.filter(course=course, is_active=True).exclude(book=book).update(
        is_active=False, updated_at=timezone.now()
    )

    link = CourseBook.objects.filter(course=course, book=book).first()
    if link is None:
        return CourseBook.objects.create(course=course, book=book)
    if not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active", "updated_at"])
    return link
