"""Database helpers."""

from __future__ import annotations

from collections.abc import Callable

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction

__all__ = ["create_or_reread"]


def create_or_reread[T](create: Callable[[], T], reread: Callable[[], T]) -> T:
    """Insert a row, or return the one a concurrent writer inserted first.

    Two launches for the same person can arrive together — Canvas does this
    when a page holds two links — and both will find no row and both will try
    to insert. The loser must end up with the winner's row rather than an error,
    which is what makes "never a second account" true under concurrency and not
    merely in the happy path.

    The insert runs in a savepoint so that losing the race does not poison the
    caller's transaction: Django rolls back to the savepoint and leaves the
    outer atomic block usable.

    If the re-read finds nothing, the original ``IntegrityError`` is raised
    rather than ``DoesNotExist``. That case means the violation was not the
    unique-constraint race this is written for — a foreign key or NOT NULL
    violation raises ``IntegrityError`` too — and reporting a missing row would
    point at the wrong cause entirely.
    """
    try:
        with transaction.atomic():
            return create()
    except IntegrityError as race:
        try:
            return reread()
        except ObjectDoesNotExist:
            raise race from None
