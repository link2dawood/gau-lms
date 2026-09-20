"""Public interface of the LTI module.

Every other module reaches platform registrations through this file and never
imports :mod:`apps.lti.models` directly (architecture rule C.1).

Two jobs live here:

* **Resolution** — given the ``iss`` and ``aud`` claims on an inbound launch,
  return the registration it must be verified against, or refuse. The pylti1p3
  adapter in ``tool_conf.py`` calls this on every launch.
* **Registration** — read the platform configuration and write it into the
  database. The configuration is data, not code (rule C.6): it is a JSON file
  whose path comes from ``LTI_PLATFORMS_FILE``.

The configuration file holds a list of objects::

    [
      {
        "issuer": "https://<canvas-host-or-issuer>",
        "client_id": "<developer key client id>",
        "deployment_ids": ["<deployment id>"],
        "auth_login_url": "https://<canvas-host>/api/lti/authorize_redirect",
        "auth_token_url": "https://<canvas-host>/login/oauth2/token",
        "jwks_url": "https://<canvas-host>/api/lti/security/jwks",
        "tool_key_id": "",
        "is_active": true
      }
    ]

``deployment_ids``, ``tool_key_id`` and ``is_active`` may be omitted; the rest
are required. The Canvas administrator supplies these values when the developer
key is created (task 1.17 documents the exchange).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from pylti1p3.names_roles import NamesRolesProvisioningService
from pylti1p3.registration import Registration
from pylti1p3.service_connector import ServiceConnector

from apps.lti import keys
from apps.lti.deep_linking import CUSTOM_NODE_PARAM
from apps.lti.models import LtiPlatform

__all__ = [
    "LaunchClaims",
    "LaunchClaimsIncomplete",
    "LtiPlatform",
    "NamesAndRolesUnavailable",
    "PlatformNotRegistered",
    "RegistrationSourceError",
    "SyncReport",
    "active_platforms_for_issuer",
    "fetch_course_members",
    "get_platform",
    "issuers_with_multiple_registrations",
    "load_registrations",
    "parse_launch_claims",
    "registration_for",
    "sync_platforms",
]


class PlatformNotRegistered(Exception):
    """No active registration matches the issuer and client id on a launch."""


class RegistrationSourceError(Exception):
    """The platform configuration is missing, unreadable or malformed."""


class LaunchClaimsIncomplete(Exception):
    """A verified launch did not carry the claims this platform needs."""


class NamesAndRolesUnavailable(Exception):
    """The roster cannot be read for this course."""


REQUIRED_KEYS = ("issuer", "client_id", "auth_login_url", "auth_token_url", "jwks_url")
OPTIONAL_KEYS = ("deployment_ids", "tool_key_id", "is_active")

# Every field the configuration owns. Anything else on a row — timestamps, the
# uuid — belongs to the platform and is never overwritten by a sync.
MANAGED_FIELDS = (*REQUIRED_KEYS, *OPTIONAL_KEYS)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def get_platform(issuer: str, client_id: str) -> LtiPlatform:
    """Return the active registration for an issuer and client id.

    Inactive registrations are invisible here rather than filtered by the
    caller, so a retired developer key cannot be accepted by a code path that
    forgot to check.
    """
    try:
        return LtiPlatform.objects.get(issuer=issuer, client_id=client_id, is_active=True)
    except LtiPlatform.DoesNotExist as exc:
        raise PlatformNotRegistered(
            f"No active LTI registration for issuer {issuer!r} and client id {client_id!r}."
        ) from exc


def active_platforms_for_issuer(issuer: str) -> list[LtiPlatform]:
    """Every active registration for an issuer.

    An institution can hold more than one Canvas developer key — during a
    rotation, or for a sandbox alongside production. A caller given more than
    one must ask for a client id rather than pick.
    """
    return list(LtiPlatform.objects.filter(issuer=issuer, is_active=True))


def issuers_with_multiple_registrations() -> list[str]:
    """Issuers holding more than one active registration.

    The LTI library needs this to know when `client_id` matters: given an
    issuer it believes has a single client, it never looks at the client id a
    launch carries, and would resolve an ambiguous issuer to the wrong
    developer key.
    """
    rows = (
        LtiPlatform.objects.filter(is_active=True)
        .values("issuer")
        .annotate(registrations=Count("id"))
        .filter(registrations__gt=1)
    )
    return [row["issuer"] for row in rows]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@dataclass
class SyncReport:
    """What a sync did, in terms an operator can check against their intent."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    # Registrations in the database that the configuration does not mention. A
    # sync never deletes them — removing a row silently breaks every launch
    # from that platform — so they are reported for a human to decide on.
    unmanaged: list[str] = field(default_factory=list)


def load_registrations(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read and validate the platform configuration file."""
    source = Path(path) if path is not None else _configured_path()
    try:
        raw = source.read_text()
    except OSError as exc:
        raise RegistrationSourceError(
            f"Cannot read the LTI platform configuration at {source}: {exc}"
        ) from exc

    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegistrationSourceError(f"{source} is not valid JSON: {exc}") from exc

    if not isinstance(parsed, list):
        raise RegistrationSourceError(
            f"{source} must contain a list of platform registrations, got {type(parsed).__name__}."
        )
    return [_normalise(entry, f"entry {index} in {source}") for index, entry in enumerate(parsed)]


def sync_platforms(registrations: list[dict[str, Any]], *, dry_run: bool = False) -> SyncReport:
    """Write registrations into the database, creating or updating in place.

    Idempotent: running it twice on unchanged configuration reports everything
    as unchanged and writes nothing.
    """
    if not registrations:
        raise RegistrationSourceError(
            "The platform configuration lists no registrations. Refusing to continue: "
            "an empty list is almost always a missing or wrongly mounted file, and "
            "acting on it would look identical to deliberately having no platforms."
        )

    # Validated here as well as in load_registrations: this function is public
    # API, so it can be handed a dict that never passed through the file reader.
    # Normalising an already-normalised entry changes nothing.
    entries = [
        _normalise(entry, f"registration {index}") for index, entry in enumerate(registrations)
    ]

    report = SyncReport()
    with transaction.atomic():
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            issuer, client_id = entry["issuer"], entry["client_id"]
            seen.add((issuer, client_id))
            label = f"{issuer} ({client_id})"
            outcome = _apply(entry)
            if outcome == "created":
                report.created.append(label)
            elif outcome == "updated":
                report.updated.append(label)
            else:
                report.unchanged.append(label)

        for platform in LtiPlatform.objects.all():
            if (platform.issuer, platform.client_id) not in seen:
                report.unmanaged.append(str(platform))

        if dry_run:
            transaction.set_rollback(True)

    return report


def _apply(entry: dict[str, Any]) -> str:
    """Create or update one registration; return the report bucket it lands in.

    Validation happens before the write in both branches, so a malformed entry
    never reaches the table even briefly.
    """
    platform = LtiPlatform.objects.filter(
        issuer=entry["issuer"], client_id=entry["client_id"]
    ).first()

    if platform is None:
        platform = LtiPlatform(**entry)
        _validate(platform, entry)
        platform.save()
        return "created"

    changed = [
        key for key in MANAGED_FIELDS if key in entry and getattr(platform, key) != entry[key]
    ]
    if not changed:
        return "unchanged"

    for key in changed:
        setattr(platform, key, entry[key])
    _validate(platform, entry)
    platform.save(update_fields=[*changed, "updated_at"])
    return "updated"


def _validate(platform: LtiPlatform, entry: dict[str, Any]) -> None:
    """Run model validation, which ``save()`` alone does not.

    Field validators — including the deployment id shape check — only run from
    ``full_clean``. Without this call a malformed configuration would be stored
    and fail later, at launch, as something far harder to diagnose.
    """
    try:
        platform.full_clean()
    except ValidationError as exc:
        raise RegistrationSourceError(
            f"Registration for issuer {entry['issuer']!r} and client id "
            f"{entry['client_id']!r} is invalid: {exc.message_dict}"
        ) from exc


def _configured_path() -> Path:
    configured = settings.LTI_PLATFORMS_FILE
    if not configured:
        raise RegistrationSourceError(
            "LTI_PLATFORMS_FILE is not set, so there is nowhere to read Canvas platform "
            "registrations from. Point it at a JSON file, or pass --file."
        )
    return Path(configured)


def _optional_defaults() -> dict[str, Any]:
    """What an omitted optional key means. A fresh dict per call — the list is
    mutable and must not be shared between registrations."""
    return {"deployment_ids": [], "tool_key_id": "", "is_active": True}


def _normalise(entry: Any, where: str) -> dict[str, Any]:
    """Validate one entry and return it complete.

    Every managed key is present in the result, filled from
    :func:`_optional_defaults` when the source omitted it. That is what makes a
    sync idempotent in the sense D-025 claims: the same file produces the same
    row whether or not that row already existed. Without it, dropping
    ``"is_active": false`` from the file would leave a platform disabled
    forever, and dropping ``deployment_ids`` would leave stale ids launching.
    """
    if not isinstance(entry, dict):
        raise RegistrationSourceError(f"{where} must be an object, got {type(entry).__name__}.")

    unknown = sorted(set(entry) - set(MANAGED_FIELDS))
    if unknown:
        raise RegistrationSourceError(
            f"{where} has keys the platform does not understand: {', '.join(unknown)}. "
            f"A typo here would silently leave the real setting at its default."
        )

    # Checked on the raw value, not on str(value): `"issuer": null` stringifies
    # to "None" and `0` to "0", both of which a length test would accept and the
    # database would then store as those literal strings.
    missing = [
        key
        for key in REQUIRED_KEYS
        if not isinstance(entry.get(key), str) or not entry[key].strip()
    ]
    if missing:
        raise RegistrationSourceError(
            f"{where} is missing or has a non-text value for: {', '.join(missing)}."
        )

    normalised = _optional_defaults()
    normalised.update({key: entry[key] for key in MANAGED_FIELDS if key in entry})

    if not isinstance(normalised["deployment_ids"], list):
        raise RegistrationSourceError(f"{where}: deployment_ids must be a list.")
    if not isinstance(normalised["tool_key_id"], str):
        raise RegistrationSourceError(f"{where}: tool_key_id must be text.")
    if not isinstance(normalised["is_active"], bool):
        raise RegistrationSourceError(f"{where}: is_active must be true or false.")

    return normalised


# ---------------------------------------------------------------------------
# Launch claims
#
# LTI 1.3 claim URIs. Part of the specification and identical on every
# platform, so not configuration and not subject to rule C.6.
# ---------------------------------------------------------------------------

CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
CLAIM_DEPLOYMENT_ID = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
CLAIM_MESSAGE_TYPE = "https://purl.imsglobal.org/spec/lti/claim/message_type"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
CLAIM_NRPS = "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice"
CLAIM_CUSTOM = "https://purl.imsglobal.org/spec/lti/claim/custom"
CLAIM_TOOL_PLATFORM = "https://purl.imsglobal.org/spec/lti/claim/tool_platform"


@dataclass(frozen=True)
class LaunchClaims:
    """What a verified launch tells us, in this platform's vocabulary.

    A plain value object rather than the raw JWT body, so that provisioning —
    which spans three modules — does not have to know LTI's claim URIs, and so
    that the shape it depends on is declared in one place.
    """

    issuer: str
    platform_guid: str
    deployment_id: str
    message_type: str
    canvas_user_id: str
    name: str
    email: str
    avatar_url: str
    canvas_course_id: str
    course_title: str
    course_label: str
    role_claims: list[str]
    # Where Canvas will list this course's members. Empty when the platform
    # does not offer Names and Roles, or the developer key lacks the scope.
    nrps_url: str
    # Which part of the textbook this resource link points at, set when the
    # link was created through deep linking. Empty for a plain course launch.
    node_id: str


def parse_launch_claims(data: Mapping[str, Any]) -> LaunchClaims:
    """Read a validated launch body into a LaunchClaims.

    Called only after PyLTI1p3 has verified the signature, so the values are
    trusted to come from the platform — but not trusted to be present or to be
    the right shape. A platform is free to omit anything optional, and course
    privacy settings routinely do.
    """
    context = _mapping(data.get(CLAIM_CONTEXT))
    platform = _mapping(data.get(CLAIM_TOOL_PLATFORM))

    issuer = _text(data.get("iss"))
    canvas_user_id = _text(data.get("sub"))
    canvas_course_id = _text(context.get("id"))

    # Without these three there is nobody to provision, nowhere to put them, or
    # no way to tell one platform's course from another's.
    missing = [
        name
        for name, value in (
            ("iss", issuer),
            ("sub", canvas_user_id),
            ("context.id", canvas_course_id),
        )
        if not value
    ]
    if missing:
        raise LaunchClaimsIncomplete(
            f"The launch is valid but carries no {', '.join(missing)}, "
            f"so it cannot be attached to a person and a course."
        )

    roles = data.get(CLAIM_ROLES)
    return LaunchClaims(
        issuer=issuer,
        platform_guid=_text(platform.get("guid")),
        deployment_id=_text(data.get(CLAIM_DEPLOYMENT_ID)),
        message_type=_text(data.get(CLAIM_MESSAGE_TYPE)),
        canvas_user_id=canvas_user_id,
        name=_text(data.get("name")),
        email=_text(data.get("email")),
        avatar_url=_text(data.get("picture")),
        canvas_course_id=canvas_course_id,
        course_title=_text(context.get("title")),
        course_label=_text(context.get("label")),
        nrps_url=_text(_mapping(data.get(CLAIM_NRPS)).get("context_memberships_url")),
        node_id=_text(_mapping(data.get(CLAIM_CUSTOM)).get(CUSTOM_NODE_PARAM)),
        role_claims=[r for r in roles if isinstance(r, str)] if isinstance(roles, list) else [],
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    """A claim that should be an object, or an empty one if it is not."""
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    """A claim that should be text. Anything else is treated as absent, rather
    than stringified into something that would be stored as `None` or `0`."""
    return value.strip() if isinstance(value, str) else ""


# ---------------------------------------------------------------------------
# Talking to the platform
# ---------------------------------------------------------------------------


def registration_for(platform: LtiPlatform) -> Registration:
    """Build the PyLTI1p3 registration for a platform row.

    One builder, used both to verify inbound launches and to sign outbound
    service calls. They must agree: if the tool signs with a key whose public
    half is not the one advertised, Canvas rejects the call for reasons that
    surface nowhere near the cause (D-027).
    """
    registration = (
        Registration()
        .set_issuer(platform.issuer)
        .set_client_id(platform.client_id)
        .set_auth_login_url(platform.auth_login_url)
        .set_auth_token_url(platform.auth_token_url)
        .set_key_set_url(platform.jwks_url)
    )
    # A launch is verified with Canvas's key, not ours, so a platform with no
    # key assigned can still be launched from — it just cannot make service
    # calls, which is what fetch_course_members refuses below.
    if platform.tool_key_id:
        registration.set_tool_private_key(keys.private_key_pem(platform.tool_key_id))
        registration.set_tool_public_key(keys.public_key_pem(platform.tool_key_id))
    return registration


def fetch_course_members(platform: LtiPlatform, memberships_url: str) -> list[dict[str, Any]]:
    """Read a course's roster from the platform's Names and Roles service.

    Returns every member across every page — PyLTI1p3 follows the pagination
    links, which Canvas does use on a large course.

    This is the only place that speaks NRPS. The reconciliation that follows
    knows nothing about LTI (see services/roster.py), and this knows nothing
    about users or memberships.
    """
    if not memberships_url:
        raise NamesAndRolesUnavailable("This course has no Names and Roles service URL.")
    if not platform.tool_key_id:
        raise NamesAndRolesUnavailable(
            f"Platform {platform.client_id!r} has no signing key, so it cannot request a "
            f"token. Generate one with `manage.py create_lti_key` and set tool_key_id."
        )

    service = NamesRolesProvisioningService(
        ServiceConnector(registration_for(platform)),
        {"context_memberships_url": memberships_url},
    )
    return [member for member in service.get_members() if isinstance(member, dict)]
