"""Canvas platform registrations.

An LTI 1.3 tool trusts exactly the platforms it has been told about. A launch
arrives as a JWT claiming an issuer, an audience (the client id Canvas assigned
to the developer key) and a deployment id; the tool may only accept it if that
triple is registered here, and it validates the signature against the JWKS of
the registered platform.

Nothing in this module names a Canvas host, client id or deployment id
(architecture rule C.6). Rows are written by
``apps.lti.services.sync_platforms`` from a configuration file, so moving from a
sandbox to production is a configuration change rather than a code change.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models


def validate_deployment_ids(value: object) -> None:
    """Reject anything that is not a list of distinct, non-empty ids.

    A JSONField will happily store a string, a number or a nested object, and
    the mistake would only surface at launch time as a failed comparison
    against a value that is not the shape the code expects.
    """
    if not isinstance(value, list):
        raise ValidationError("deployment_ids must be a list of Canvas deployment ids.")
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError("Every deployment id must be a non-empty string.")
        if item in seen:
            raise ValidationError(f"Deployment id {item!r} is listed twice.")
        seen.add(item)


class LtiPlatform(models.Model):
    # Stable internal identifier (rule C.2). The launch log (task 1.15) and any
    # later per-platform record point at this, not at the issuer string, which
    # an institution can change.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The `iss` claim. Deliberately a CharField and not a URLField: OIDC treats
    # the issuer as an opaque identifier compared by exact string match, and a
    # URL validator would reject a legitimate issuer that is not a URL while
    # giving no protection against the wrong one.
    issuer = models.CharField(max_length=512)

    # The `aud` claim — the client id of the Canvas developer key. One issuer
    # may have several, so neither column is unique on its own; the pair is.
    client_id = models.CharField(max_length=255)

    # Canvas issues one deployment id per installation of the tool (account or
    # course level), and more can appear at any time. May legitimately be empty
    # between registering the platform and installing the tool in Canvas — a
    # launch against an empty list finds no matching deployment and is
    # refused by the pylti1p3 adapter.
    deployment_ids = models.JSONField(default=list, validators=[validate_deployment_ids])

    # Where the tool sends the browser to begin the OIDC handshake (task 1.4).
    auth_login_url = models.URLField(max_length=512)
    # Where the tool exchanges a signed client assertion for an access token,
    # used by the Names and Roles sync (task 1.13).
    auth_token_url = models.URLField(max_length=512)
    # Canvas's public keys, used to verify the signature on a launch (task 1.5).
    jwks_url = models.URLField(max_length=512)

    # The `kid` of the tool's own keypair used when signing requests to this
    # platform. A reference only: the private key itself never enters the
    # database, because a database dump is handled far less carefully than a
    # key file. Task 1.3 generates the pair and fills this in.
    tool_key_id = models.CharField(max_length=64, blank=True)

    # Retiring a registration without deleting it: a superseded developer key
    # must stop accepting launches while its launch history stays readable.
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LTI platform"
        verbose_name_plural = "LTI platforms"
        ordering = ("issuer", "client_id")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["issuer", "client_id"],
                name="unique_lti_registration",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.issuer} ({self.client_id})"

    def accepts_deployment(self, deployment_id: str) -> bool:
        return deployment_id in self.deployment_ids


class LaunchOutcome(models.TextChoices):
    """How a launch ended.

    Deliberately distinguishes the refusals an administrator would act on
    differently. "Refused" on its own sends someone to check the wrong thing.
    """

    ACCEPTED = "ACCEPTED", "Accepted"
    DEEP_LINK = "DEEP_LINK", "Deep linking request answered"
    REFUSED_VALIDATION = "REFUSED_VALIDATION", "Refused: could not be verified"
    REFUSED_CONFIGURATION = "REFUSED_CONFIGURATION", "Refused: platform not configured"
    REFUSED_CLAIMS = "REFUSED_CLAIMS", "Refused: launch carried too little"
    ERROR = "ERROR", "Failed unexpectedly"


class LtiLaunchLog(models.Model):
    """An append-only record of every launch this tool was asked to serve.

    Written for the questions that get asked after something went wrong: did
    this person reach the tool at all, from which course, with what standing,
    and if not, why not. A launch that Canvas rejected leaves no trace anywhere
    else, so without this a failed launch is only a support ticket.

    **No foreign keys, deliberately.** A user id and a course id are recorded
    as plain columns, not relations. An audit record must outlive what it
    describes and must never be the reason another operation fails, and a
    refused launch frequently has no user or course to point at. It also keeps
    the lti module free of a schema dependency on accounts and courses.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    outcome = models.CharField(max_length=32, choices=LaunchOutcome.choices)

    # Who and where, as Canvas named them. Kept even when the soft references
    # below are empty, which is the usual case for a refusal.
    issuer = models.CharField(max_length=512, blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    deployment_id = models.CharField(max_length=255, blank=True)
    canvas_user_id = models.CharField(max_length=255, blank=True)

    # The nonce the launch carried. Recorded so a replay attempt is visible as
    # two rows sharing one nonce — the single-use check (D-030) refuses the
    # second, and this is what shows that it happened.
    nonce = models.CharField(max_length=255, blank=True)

    # Soft references. Null on any launch that never got as far as resolving
    # them. No constraint, by design: see the class docstring.
    user_id = models.UUIDField(null=True, blank=True)
    course_id = models.UUIDField(null=True, blank=True)
    role = models.CharField(max_length=16, blank=True)

    # Why, for a refusal. Never carries a name, an email or a token — this is
    # read by operators, and an audit log is a poor place to accumulate
    # personal data.
    detail = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "LTI launch log"
        verbose_name_plural = "LTI launch logs"
        ordering = ("-created_at",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["-created_at"], name="lti_launch_recent_idx"),
            models.Index(fields=["canvas_user_id"], name="lti_launch_user_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.outcome} {self.issuer} {self.created_at:%Y-%m-%d %H:%M}"
