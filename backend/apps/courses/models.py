"""Canvas courses and who is in them.

Canvas is the authority (architecture rule C.5). Nothing here is ever created
by hand or edited in an admin: rows appear when someone launches the tool
(task 1.8) and are reconciled against the Canvas roster (task 1.13). A course
title is a copy of what Canvas said, kept so the reader can name the course
without a round trip, not a fact this platform owns.

Neither model is ever deleted. A membership that disappears from the Canvas
roster is deactivated, because a reading position points at a person in a
course, and deleting the membership would orphan it.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    """What someone may do, in this platform's terms.

    Deliberately small and deliberately not Canvas's vocabulary. Canvas sends a
    list of role URIs that varies by installation; task 1.7 maps them onto
    these three, defaulting to the least privileged. Everything downstream —
    permissions, routing, the CMS gate — reads these, so a change in how Canvas
    spells a role touches one mapping rather than every check.
    """

    STUDENT = "STUDENT", "Student"
    FACULTY = "FACULTY", "Faculty"
    ADMIN = "ADMIN", "Administrator"


class Course(models.Model):
    # Stable internal identifier (rule C.2). Content mappings and reading
    # positions point here, never at the Canvas id, which is Canvas's to change.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # A Canvas course id is only unique within one Canvas, so it needs a scope.
    # Three columns together form the identity, for three different reasons.
    #
    # `issuer` separates platforms that are genuinely different products or
    # self-hosted installations.
    #
    # `platform_guid` — the `guid` of the tool_platform claim — separates
    # instances that share an issuer. Canvas Cloud is the case that forces
    # this: every Instructure-hosted Canvas presents the same `iss`, so the
    # issuer alone cannot tell one university's course 42 from another's. Two
    # institutions would silently merge onto one row, taking their rosters and
    # every reading position with them.
    #
    # `canvas_course_id` is the `context.id` claim.
    #
    # What is deliberately NOT in the identity is the registration or the
    # deployment. Both change under ordinary maintenance — rotating a developer
    # key, reinstalling the tool — and a course whose identity changed would
    # strand every reading position pointing at the old one.
    issuer = models.CharField(max_length=512)
    platform_guid = models.CharField(max_length=255, blank=True)
    canvas_course_id = models.CharField(max_length=255)

    # Recorded for diagnosing a launch and for the roster sync to know which
    # deployment a course was last seen from. Not part of identity, and
    # overwritten by each launch.
    canvas_deployment_id = models.CharField(max_length=255, blank=True)

    # Where Canvas will list this course's members, from the Names and Roles
    # claim on a launch. Blank until a launch carries it: the service is an LTI
    # Advantage extra, and a platform or a developer key without the scope
    # simply never sends it. The roster sync skips a course with no URL rather
    # than treating that as an empty roster — see DECISIONS.md D-049.
    nrps_context_memberships_url = models.URLField(max_length=1024, blank=True)

    # When the roster was last reconciled against Canvas. Null means never.
    roster_synced_at = models.DateTimeField(null=True, blank=True)

    # Both may be withheld: what Canvas sends in the context claim depends on
    # the course's privacy settings.
    title = models.CharField(max_length=512, blank=True)
    label = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("title", "canvas_course_id")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["issuer", "platform_guid", "canvas_course_id"],
                name="unique_course_per_platform_instance",
            ),
        ]

    def __str__(self) -> str:
        return self.title or self.label or self.canvas_course_id


class CourseMembership(models.Model):
    """One person's place in one course, as Canvas most recently described it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT on both, not CASCADE. Neither a user nor a course is ever deleted
    # by this platform, and if something ever tries, it should fail loudly
    # rather than quietly take a person's reading history with it.
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )

    # Defaults to the least privileged value, so a role that fails to map, or a
    # row created before its role is known, grants nothing extra.
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)

    # False once Canvas stops listing the person on the roster (task 1.13).
    # The row stays: it is what a reading position hangs from.
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "id")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["course", "user"],
                name="unique_course_membership",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.course} as {self.role}"
