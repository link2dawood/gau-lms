"""Recording what happened to a launch.

Separate from the launch flow on purpose. Writing this record must never be
able to stop a launch that would otherwise have worked, and it must never be
something the launch path depends on — so every failure here is swallowed after
being logged, and nothing returns a value the caller acts on.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.lti.models import LaunchOutcome, LtiLaunchLog

logger = logging.getLogger(__name__)

__all__ = ["LaunchOutcome", "record_launch"]

# Long enough to say what went wrong, short enough that a traceback or a token
# cannot be smuggled into the column whole.
MAX_DETAIL = 500


def record_launch(
    *,
    outcome: LaunchOutcome,
    issuer: str = "",
    client_id: str = "",
    deployment_id: str = "",
    canvas_user_id: str = "",
    nonce: str = "",
    user_id: str | None = None,
    course_id: str | None = None,
    role: str = "",
    detail: str = "",
) -> None:
    """Append one launch record. Never raises.

    An audit row that fails to write is worth a log line and nothing more.
    Letting it propagate would mean a database hiccup turns a successful launch
    into an error page — trading the thing being protected for the record of it.
    """
    try:
        LtiLaunchLog.objects.create(
            outcome=outcome,
            issuer=issuer[:512],
            client_id=client_id[:255],
            deployment_id=deployment_id[:255],
            canvas_user_id=canvas_user_id[:255],
            nonce=nonce[:255],
            user_id=user_id,
            course_id=course_id,
            role=role[:16],
            detail=detail[:MAX_DETAIL],
        )
    except Exception:
        logger.exception("Could not write the launch audit record (%s).", outcome)


def claims_of(launch: Any) -> dict[str, str]:
    """The identifying claims of a launch, for a record, best effort.

    Called on the failure path, where the launch may be half-validated or not
    validated at all, so every read is defensive and an unreadable claim simply
    does not appear.
    """
    try:
        body = launch.get_launch_data()
    except Exception:
        return {}
    if not isinstance(body, dict):
        return {}

    def text(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    audience = body.get("aud")
    return {
        "issuer": text(body.get("iss")),
        "client_id": text(audience[0] if isinstance(audience, list) and audience else audience),
        "deployment_id": text(body.get("https://purl.imsglobal.org/spec/lti/claim/deployment_id")),
        "canvas_user_id": text(body.get("sub")),
        "nonce": text(body.get("nonce")),
    }
