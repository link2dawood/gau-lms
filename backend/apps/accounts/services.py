"""Public interface of the accounts module.

Other modules reach users through this file and never import
``apps.accounts.models`` directly (architecture rule C.1).
"""

from __future__ import annotations

import logging

from apps.accounts.models import User
from utils.db import create_or_reread

logger = logging.getLogger(__name__)

__all__ = ["User", "get_user", "upsert_user"]

# Fields Canvas owns and this platform only copies. `is_content_admin` is
# deliberately absent: no Canvas role confers CMS access (D-023), so a launch
# can never grant it, whatever claims it carries.
CANVAS_OWNED_FIELDS = ("name", "email", "avatar_url")


def upsert_user(
    *, canvas_user_id: str, name: str = "", email: str = "", avatar_url: str = ""
) -> User:
    """Find or create the account for a Canvas person.

    The "no second account" acceptance criterion lives here. Two launches
    arriving at once — Canvas can do that when a page holds two links — would
    both find no user and both try to create one; the unique constraint makes
    the loser fail, and it re-reads rather than raising.
    """
    if not canvas_user_id:
        raise ValueError("A launch with no `sub` claim cannot identify a person.")

    supplied = {"name": name, "email": email, "avatar_url": avatar_url}
    user = User.objects.filter(canvas_user_id=canvas_user_id).first()

    if user is None:
        # Always through the manager, never Model.objects.create: only
        # create_user marks the password unusable, and an empty password is one
        # Django considers usable.
        return create_or_reread(
            create=lambda: User.objects.create_user(canvas_user_id=canvas_user_id, **supplied),
            reread=lambda: User.objects.get(canvas_user_id=canvas_user_id),
        )

    # Refresh what Canvas sent, but never blank a field Canvas has stopped
    # sending. Course privacy settings differ, so the same person can arrive
    # with a name from one course and without it from another; forgetting the
    # name because of where they launched from would be a regression.
    changed = [
        field for field, value in supplied.items() if value and getattr(user, field) != value
    ]
    if changed:
        for field in changed:
            setattr(user, field, supplied[field])
        user.save(update_fields=[*changed, "updated_at"])

    return user


def get_user(user_id: str) -> User | None:
    """Look a user up by internal id, or None if there is no such user.

    Used when a launch ticket is redeemed (task 1.9): the ticket carries an id,
    and the account it names may have been deactivated in the meantime.
    """
    return User.objects.filter(pk=user_id, is_active=True).first()
