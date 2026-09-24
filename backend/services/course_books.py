"""Which textbook a launched course opens, and whether it may be read.

Two facts have to agree before a student sees anything, and they belong to
different modules: the courses module knows which book a course is mapped to,
and the content module knows whether that book is published (D-053). Neither
owns the question, so it lives here — the package D-033 set aside for exactly
this, naming task 2.5 as its next occupant.

The answer is a small result rather than a `Book | None`, for the reason D-014
gives on the frontend: "this course has no textbook yet" and "the textbook is
not published yet" need different screens and different fixes, and flattening
them into None moves that decision to a guess at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apps.content.services import Book
from apps.courses.services import Course, active_book_link

__all__ = ["BookAvailability", "CourseBookResolution", "book_for_course"]


class BookAvailability(StrEnum):
    """Why a course does or does not open a readable textbook."""

    AVAILABLE = "AVAILABLE"

    # No mapping. The course has been launched but nobody has said which book
    # it teaches from — an administrator's job (task 3.2).
    NO_BOOK_LINKED = "NO_BOOK_LINKED"

    # Mapped, but the book is a draft or has been archived. The fix is a
    # publication, not a mapping, and saying so is the difference between an
    # administrator looking in the right place and the wrong one.
    BOOK_NOT_PUBLISHED = "BOOK_NOT_PUBLISHED"


@dataclass(frozen=True)
class CourseBookResolution:
    """What a course opens, if anything.

    `book` is populated **only** when the book may be read. A caller that
    ignores `availability` and reaches for `book` therefore gets nothing rather
    than an unpublished textbook, which is the right way round to be wrong.
    Task 3.9's draft preview is a deliberate, separately named path — not a
    flag on this one, because a boolean that widens access is a boolean
    somebody eventually passes True by accident.
    """

    availability: BookAvailability
    book: Book | None = None

    @property
    def is_available(self) -> bool:
        return self.availability is BookAvailability.AVAILABLE


def book_for_course(course: Course) -> CourseBookResolution:
    """Resolve the textbook this course opens, applying the publication gate.

    The outer of D-053's two gates. The inner one — whether a given node has a
    published version — is `apps.versioning.services`, applied per node by task
    2.6. Both must say yes before a student reads anything.
    """
    link = active_book_link(course)
    if link is None:
        return CourseBookResolution(BookAvailability.NO_BOOK_LINKED)
    if not link.book.is_readable:
        return CourseBookResolution(BookAvailability.BOOK_NOT_PUBLISHED)
    return CourseBookResolution(BookAvailability.AVAILABLE, link.book)
