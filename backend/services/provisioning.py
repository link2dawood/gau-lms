"""Turn a verified launch into the records the platform works from.

This is the whole of acceptance criterion 1 — "a Canvas user launches without
creating a second account" — and criterion 3, that the course context Canvas
sent is the one used.

It spans three modules, so it lives outside all of them (see this package's
docstring). It reaches each through that module's ``services.py`` and never
touches another module's models (rule C.1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction

from apps.accounts.services import User, upsert_user
from apps.courses.services import (
    Course,
    CourseMembership,
    Role,
    normalise_role,
    upsert_course,
    upsert_membership,
)
from apps.lti.services import LaunchClaims

logger = logging.getLogger(__name__)

__all__ = ["LaunchContext", "provision_launch"]


@dataclass(frozen=True)
class LaunchContext:
    """Who launched, into which course, with what standing."""

    user: User
    course: Course
    membership: CourseMembership

    @property
    def role(self) -> Role:
        return Role(self.membership.role)


@transaction.atomic
def provision_launch(claims: LaunchClaims) -> LaunchContext:
    """Upsert the person, the course and the membership, together.

    One transaction, deliberately. A launch that created a user and then failed
    to record their membership would leave an account that belongs to no
    course — and the next launch would find that account, skip creation, and
    fail the same way, so the person could never get in. Either all three rows
    exist or the launch is refused and can be retried cleanly.

    Every field written here is Canvas's, and that includes the course role:
    it is rewritten from the claims on each launch, so a demotion in Canvas
    takes effect as promptly as a promotion.

    What a launch can never confer is PLATFORM privilege. `is_content_admin`
    gates the CMS, it is granted by an operator, and no claim touches it
    (D-023). A Canvas account administrator therefore arrives with the ADMIN
    course role and still no ability to edit the textbook.
    """
    user = upsert_user(
        canvas_user_id=claims.canvas_user_id,
        name=claims.name,
        email=claims.email,
        avatar_url=claims.avatar_url,
    )
    course = upsert_course(
        issuer=claims.issuer,
        platform_guid=claims.platform_guid,
        canvas_course_id=claims.canvas_course_id,
        title=claims.course_title,
        label=claims.course_label,
        deployment_id=claims.deployment_id,
        nrps_url=claims.nrps_url,
    )
    membership = upsert_membership(
        course=course,
        user=user,
        role=normalise_role(claims.role_claims),
    )

    logger.info(
        "Launch provisioned: user=%s course=%s role=%s",
        user.pk,
        course.pk,
        membership.role,
    )
    return LaunchContext(user=user, course=course, membership=membership)
