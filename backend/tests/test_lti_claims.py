"""Reading a verified launch, and mapping Canvas's vocabulary onto ours.

These run without a database. They are the checks that catch a Canvas that
sends something slightly different from the happy path — which is most of what
goes wrong in an LTI integration, and none of which surfaces as an exception.
"""

from __future__ import annotations

import pytest

from apps.courses.services import Role, normalise_role
from apps.lti.services import (
    CLAIM_CONTEXT,
    CLAIM_CUSTOM,
    CLAIM_NRPS,
    CLAIM_ROLES,
    LaunchClaimsIncomplete,
    parse_launch_claims,
)
from tests.factories import launch_body

MEMBERSHIP = "http://purl.imsglobal.org/vocab/lis/v2/membership"
INSTITUTION = "http://purl.imsglobal.org/vocab/lis/v2/institution/person"
SYSTEM = "http://purl.imsglobal.org/vocab/lti/system/person"


class TestParsingAVerifiedLaunch:
    def test_a_complete_launch_yields_every_field(self) -> None:
        claims = parse_launch_claims(launch_body())
        assert claims.issuer == "https://canvas.instructure.com"
        assert claims.canvas_user_id == "535fa085-1a81-4c07-bb56-b0d4ae1c8e1c"
        assert claims.canvas_course_id == "4321"
        assert claims.course_title == "Fundamentals of Nursing"
        assert claims.platform_guid == "abc.gau.instructure.com"
        assert claims.deployment_id == "12:abc"

    @pytest.mark.parametrize(
        ("field", "value"),
        [("iss", ""), ("sub", ""), ("sub", 12345), (CLAIM_CONTEXT, {}), (CLAIM_CONTEXT, "NURS")],
    )
    def test_a_launch_that_cannot_be_attached_is_refused(self, field: str, value: object) -> None:
        """Without an issuer, a person and a course there is nothing to provision.

        `sub` arriving as a number matters: a length check on `str(value)` would
        have accepted it and stored the literal "12345" as someone's identity.
        """
        with pytest.raises(LaunchClaimsIncomplete):
            parse_launch_claims(launch_body(**{field: value}))

    def test_privacy_settings_hiding_name_and_email_are_not_an_error(self) -> None:
        """Canvas withholds these per course. Refusing would deny a whole course."""
        claims = parse_launch_claims(launch_body(name="", email=""))
        assert (claims.name, claims.email) == ("", "")
        assert claims.canvas_course_id == "4321"

    def test_a_platform_without_names_and_roles_still_launches(self) -> None:
        body = launch_body()
        del body[CLAIM_NRPS]
        assert parse_launch_claims(body).nrps_url == ""

    @pytest.mark.parametrize("roles", ["Learner", 7, None, {}])
    def test_a_roles_claim_that_is_not_a_list_degrades_to_none(self, roles: object) -> None:
        assert parse_launch_claims(launch_body(**{CLAIM_ROLES: roles})).role_claims == []

    def test_non_string_roles_are_dropped_not_stringified(self) -> None:
        body = launch_body(**{CLAIM_ROLES: [None, 7, "Instructor"]})
        assert parse_launch_claims(body).role_claims == ["Instructor"]

    def test_a_deep_linked_node_arrives_on_the_launch(self) -> None:
        body = launch_body(**{CLAIM_CUSTOM: {"node_id": "a-node-uuid"}})
        assert parse_launch_claims(body).node_id == "a-node-uuid"

    def test_a_plain_launch_carries_no_node(self) -> None:
        assert parse_launch_claims(launch_body()).node_id == ""


class TestRoleNormalisation:
    @pytest.mark.parametrize(
        ("claims", "expected"),
        [
            ([f"{INSTITUTION}#Student", f"{MEMBERSHIP}#Learner"], Role.STUDENT),
            ([f"{MEMBERSHIP}#Instructor"], Role.FACULTY),
            ([f"{MEMBERSHIP}/Instructor#TeachingAssistant"], Role.FACULTY),
            ([f"{MEMBERSHIP}#ContentDeveloper"], Role.FACULTY),
            ([f"{SYSTEM}#Administrator"], Role.ADMIN),
            (["Instructor"], Role.FACULTY),
            (["  Instructor  "], Role.FACULTY),
        ],
    )
    def test_canvas_enrolments_map_as_expected(self, claims: list[str], expected: Role) -> None:
        assert normalise_role(claims) == expected

    def test_an_observer_is_not_faculty(self) -> None:
        """Canvas's Mentor role is an observer — a parent, typically. The name
        invites the opposite reading, which is why it is asserted."""
        assert normalise_role([f"{MEMBERSHIP}#Mentor"]) == Role.STUDENT

    def test_institutional_staff_are_not_teaching_staff(self) -> None:
        """A registrar or IT employee carries this. Mapping it to FACULTY gave
        anyone the institution employed the faculty view of every course."""
        assert normalise_role([f"{INSTITUTION}#Staff"]) == Role.STUDENT

    def test_the_most_privileged_recognised_role_wins(self) -> None:
        """Canvas permits a teacher to also be enrolled as a student."""
        assert normalise_role([f"{MEMBERSHIP}#Learner", f"{MEMBERSHIP}#Instructor"]) == Role.FACULTY
        assert normalise_role([f"{MEMBERSHIP}#Learner", f"{SYSTEM}#Administrator"]) == Role.ADMIN

    @pytest.mark.parametrize(
        "claims",
        [None, [], ["urn:x:Hamster"], [""], [None], [{}], ["instructor"], ["INSTRUCTOR"]],
    )
    def test_anything_unrecognised_yields_the_least_privilege(self, claims: object) -> None:
        """Including a role spelt in the wrong case: exact match only, so a
        near-miss can never escalate."""
        assert normalise_role(claims) == Role.STUDENT  # type: ignore[arg-type]

    def test_an_unknown_role_beside_a_known_one_does_not_suppress_it(self) -> None:
        assert normalise_role(["urn:x:Unknown", f"{MEMBERSHIP}#Instructor"]) == Role.FACULTY
