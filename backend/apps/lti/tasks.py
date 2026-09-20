"""Background work that talks to Canvas.

Routed to the `canvas` queue by module path (core/celery.py), so a long roster
sync on a large course cannot sit behind a 338-page document import.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from apps.courses.services import courses_with_roster_service, get_course
from apps.lti.services import (
    NamesAndRolesUnavailable,
    PlatformNotRegistered,
    active_platforms_for_issuer,
)
from services.roster import sync_course_roster as reconcile

logger = logging.getLogger(__name__)

# Canvas can be slow or briefly unavailable. Retries are spaced widely because
# a roster is not urgent — being an hour out of date costs nothing, and
# hammering the platform during an outage costs everyone.
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 300


@shared_task(bind=True, max_retries=MAX_RETRIES)
def sync_course_roster(self: Any, course_id: str, client_id: str) -> dict[str, int]:
    """Reconcile one course's membership against Canvas.

    Run on demand and from the scheduled sweep below.
    """
    course = get_course(course_id)
    if course is None:
        # Not retried: a course that no longer exists will not reappear.
        logger.warning("Roster sync skipped: course %s does not exist.", course_id)
        return {"members_seen": 0, "memberships_active": 0, "memberships_deactivated": 0}

    try:
        report = reconcile(course, client_id)
    except (NamesAndRolesUnavailable, PlatformNotRegistered) as exc:
        # Configuration, not weather. Retrying changes nothing, and a retry
        # storm would bury the log line that says what to fix.
        logger.warning("Roster sync unavailable for course %s: %s", course_id, exc)
        return {"members_seen": 0, "memberships_active": 0, "memberships_deactivated": 0}
    except Exception as exc:
        logger.warning("Roster sync for course %s failed, will retry: %s", course_id, exc)
        raise self.retry(exc=exc, countdown=RETRY_BACKOFF_SECONDS) from exc

    return {
        "members_seen": report.members_seen,
        "memberships_active": report.memberships_active,
        "memberships_deactivated": report.memberships_deactivated,
    }


@shared_task
def sync_all_rosters() -> int:
    """Queue a sync for every course Canvas will give us a roster for.

    Fans out one task per course rather than looping here, so one course's
    failure cannot stop the rest and each retries on its own schedule.
    """
    queued = 0
    for course in courses_with_roster_service():
        for client_id in _client_ids_for(course):
            sync_course_roster.delay(str(course.pk), client_id)
            queued += 1

    logger.info("Queued %d roster syncs.", queued)
    return queued


def _client_ids_for(course: Any) -> list[str]:
    """Which registrations could serve this course's roster.

    A course is identified by issuer and platform instance, not by developer
    key (D-032), so an issuer holding more than one registration offers more
    than one candidate. The first that can produce a token wins; the others
    fail as unavailable and are logged, not retried.
    """
    return [platform.client_id for platform in active_platforms_for_issuer(course.issuer)]
