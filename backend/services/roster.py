"""Reconciling a course's membership against the Canvas roster.

A launch only ever tells us about the person launching. The roster is how the
platform learns about everyone else, and — more importantly — how it learns
that someone has left.

This knows nothing about LTI. `apps.lti.services.fetch_course_members` speaks
the protocol and hands back plain dictionaries; everything here is about
records, which is why it spans three modules and therefore lives outside all of
them (see this package's docstring).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.accounts.services import upsert_user
from apps.courses.services import (
    Course,
    deactivate_memberships_absent_from,
    mark_roster_synced,
    normalise_role,
    upsert_membership,
)
from apps.lti.services import fetch_course_members, get_platform

logger = logging.getLogger(__name__)

__all__ = ["RosterReport", "sync_course_roster"]

# Canvas reports a member's standing in the course. Anything other than Active
# means they are no longer taking part, and only Active keeps a membership on.
STATUS_ACTIVE = "Active"


@dataclass(frozen=True)
class RosterReport:
    """What one reconciliation did, in terms an administrator can check."""

    members_seen: int
    memberships_active: int
    memberships_deactivated: int
    skipped: int


def sync_course_roster(course: Course, client_id: str) -> RosterReport:
    """Bring a course's memberships into line with Canvas.

    The fetch happens **outside** the transaction. It is a network call to
    Canvas that can take seconds on a large course, and holding a database
    transaction open across it would put every row involved under lock for the
    duration.
    """
    platform = get_platform(course.issuer, client_id)
    members = fetch_course_members(platform, course.nrps_context_memberships_url)

    present: set[str] = set()
    skipped = 0

    with transaction.atomic():
        for member in members:
            user_id = _text(member.get("user_id"))
            if not user_id:
                # Nothing to attach a membership to. Counted rather than
                # raised: one malformed entry must not abandon the roster.
                skipped += 1
                continue

            if _text(member.get("status")) not in ("", STATUS_ACTIVE):
                # Reported, but no longer taking part. Leaving them out of
                # `present` is what deactivates them below.
                continue

            user = upsert_user(
                canvas_user_id=user_id,
                name=_text(member.get("name")),
                email=_text(member.get("email")),
                avatar_url=_text(member.get("picture")),
            )
            upsert_membership(
                course=course,
                user=user,
                role=normalise_role(_roles(member)),
            )
            present.add(str(user.pk))

        deactivated = deactivate_memberships_absent_from(course, present)
        mark_roster_synced(course)

    logger.info(
        "Roster synced for course %s: %d seen, %d active, %d deactivated, %d skipped",
        course.pk,
        len(members),
        len(present),
        deactivated,
        skipped,
    )
    return RosterReport(
        members_seen=len(members),
        memberships_active=len(present),
        memberships_deactivated=deactivated,
        skipped=skipped,
    )


def _roles(member: dict[str, Any]) -> list[str]:
    roles = member.get("roles")
    return [role for role in roles if isinstance(role, str)] if isinstance(roles, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
