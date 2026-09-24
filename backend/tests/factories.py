"""Test data factories and launch fixtures.

Factories build rows the way the platform would, not the way a fixture file
would: a user gets a Canvas identity and an unusable password, exactly as
launch provisioning creates one.
"""

from __future__ import annotations

from typing import Any

import factory
from django.contrib.auth import get_user_model

from apps.content.models import Book, BookStatus, ContentNode, NodeType
from apps.courses.models import Course, CourseBook, CourseMembership, Role
from apps.lti.models import LtiPlatform
from apps.lti.services import (
    CLAIM_CONTEXT,
    CLAIM_DEPLOYMENT_ID,
    CLAIM_MESSAGE_TYPE,
    CLAIM_NRPS,
    CLAIM_ROLES,
    CLAIM_TOOL_PLATFORM,
)
from apps.versioning.models import ContentVersion

User = get_user_model()

ISSUER = "https://canvas.instructure.com"
PLATFORM_GUID = "abc.gau.instructure.com"
DEPLOYMENT_ID = "12:abc"
LEARNER = "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
INSTRUCTOR = "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"


class UserFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = User
        django_get_or_create = ("canvas_user_id",)

    canvas_user_id = factory.Sequence(lambda n: f"canvas-sub-{n:06d}")
    name = factory.Faker("name")
    email = factory.Faker("email")
    password = factory.django.Password(None)


class LtiPlatformFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = LtiPlatform

    issuer = ISSUER
    client_id = factory.Sequence(lambda n: f"1000000000{n:04d}")
    deployment_ids = factory.List([DEPLOYMENT_ID])
    auth_login_url = "https://canvas.test/api/lti/authorize_redirect"
    auth_token_url = "https://canvas.test/login/oauth2/token"
    jwks_url = "https://canvas.test/api/lti/security/jwks"
    is_active = True


class CourseFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Course

    issuer = ISSUER
    platform_guid = PLATFORM_GUID
    canvas_course_id = factory.Sequence(lambda n: f"{4000 + n}")
    title = factory.Sequence(lambda n: f"Course {n}")
    label = factory.Sequence(lambda n: f"NURS-{100 + n}")


class CourseMembershipFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = CourseMembership

    course = factory.SubFactory(CourseFactory)
    user = factory.SubFactory(UserFactory)
    role = Role.STUDENT


class BookFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Book
        django_get_or_create = ("slug",)

    title = factory.Sequence(lambda n: f"Textbook {n}")
    slug = factory.Sequence(lambda n: f"textbook-{n}")
    description = ""
    status = BookStatus.DRAFT


class CourseBookFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """A course pointing at the textbook it opens."""

    class Meta:
        model = CourseBook

    course = factory.SubFactory(CourseFactory)
    book = factory.SubFactory(BookFactory)
    is_active = True


class ContentNodeFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """A node with a path already built, as the hierarchy service would leave it."""

    class Meta:
        model = ContentNode

    book = factory.SubFactory(BookFactory)
    parent = None
    node_type = NodeType.UNIT
    title = factory.Sequence(lambda n: f"Node {n}")
    position = factory.Sequence(lambda n: n + 1)
    path = factory.LazyAttribute(
        lambda node: ContentNode.build_path(node.parent.path if node.parent else "", node.position)
    )


def launch_body(**overrides: Any) -> dict[str, Any]:
    """A launch body shaped the way Canvas sends one.

    Shared so that a test asserting on provisioning and a test asserting on
    claim parsing cannot drift apart about what Canvas actually sends.
    """
    body: dict[str, Any] = {
        "iss": ISSUER,
        "sub": "535fa085-1a81-4c07-bb56-b0d4ae1c8e1c",
        "name": "A Student",
        "email": "student@gau.edu.tr",
        "picture": "https://example.test/avatar.png",
        CLAIM_CONTEXT: {"id": "4321", "title": "Fundamentals of Nursing", "label": "NURS-101"},
        CLAIM_TOOL_PLATFORM: {"guid": PLATFORM_GUID},
        CLAIM_NRPS: {"context_memberships_url": "https://canvas.test/memberships"},
        CLAIM_DEPLOYMENT_ID: DEPLOYMENT_ID,
        CLAIM_MESSAGE_TYPE: "LtiResourceLinkRequest",
        CLAIM_ROLES: [LEARNER],
    }
    body.update(overrides)
    return body


def tiptap_document(*paragraphs: str) -> dict[str, Any]:
    """A Tiptap document, shaped the way the editor (task 3.5) emits one.

    Shared so that a test asserting on versioning and a test asserting on the
    renderer cannot drift apart about what a body actually looks like. Each
    top-level node carries a `blockId`, because that is what the reader anchors
    to (task 2.7) and what the search index points at (task 2.11).
    """
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "attrs": {"blockId": f"block-{index}"},
                "content": [{"type": "text", "text": text}],
            }
            for index, text in enumerate(paragraphs or ("Placeholder.",), start=1)
        ],
    }


class ContentVersionFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """A version of a node's body, numbered as task 3.6 will number them.

    The number is derived rather than sequenced globally, so a node's versions
    read 1, 2, 3 in a test the way they will in the product. Allocation itself
    belongs to 3.6; this only keeps test data honest.
    """

    class Meta:
        model = ContentVersion

    node = factory.SubFactory(ContentNodeFactory)
    version_number = factory.LazyAttribute(
        lambda version: ContentVersion.objects.filter(node=version.node).count() + 1
    )
    body = factory.LazyFunction(tiptap_document)
    created_by = factory.SubFactory(UserFactory)
    change_note = ""
    is_published = False
    previous_version = None
