"""The read API: what a launched reader may see, and nothing else.

Three endpoints, all course-scoped:

* ``GET /api/textbook/``            which book this launch opens, if any
* ``GET /api/books/<id>/toc/``      that book's table of contents
* ``GET /api/nodes/<id>/``          one node's published body, with prev/next

**This is where acceptance criterion 12 becomes demonstrable.** D-044 recorded
that nothing in the platform could emit a cross-course refusal, because the
permission's object half had no caller. These endpoints can: a reader launched
into one course who asks for another course's book is refused by name.

The scope is never taken from the request. Which course a reader is in comes
from the session a signed launch wrote (D-043); the book comes from that course
(D-057). A book id in the URL is therefore only ever *checked*, never trusted —
there is no parameter here that can widen what a reader reaches.

Both of D-053's gates are applied, in one place each. The book must be
published, which `book_for_course` decides; and each node must have a published
version, which filters the reading order once, before anything is derived from
it (D-055). A node absent from that order has no neighbours rather than the
wrong ones, so the Next button cannot walk a student into a draft.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.content.services import Book, ContentNode, TocEntry, neighbours, nest, reading_order
from apps.courses.services import Course, get_course
from apps.lti.middleware import launch_scope
from apps.lti.permissions import CourseScoped
from apps.versioning.services import published_node_ids, published_version
from services.course_books import BookAvailability, book_for_course

logger = logging.getLogger(__name__)

__all__ = ["BookTocView", "NodeView", "TextbookView"]

# What to tell a reader whose course opens nothing readable. Both are ordinary
# states rather than errors, and they have different fixes — which is the whole
# reason D-057 kept them apart instead of collapsing them into "no book".
UNAVAILABLE_DETAIL = {
    BookAvailability.NO_BOOK_LINKED: (
        "No textbook has been linked to this course yet. Your instructor or a "
        "content administrator can set one."
    ),
    BookAvailability.BOOK_NOT_PUBLISHED: (
        "This course's textbook has not been published yet. It will appear here once it is."
    ),
}

# Deliberately the same wording as the permission class uses, so that a refusal
# reads identically whether it came from the object check or from here.
WRONG_COURSE_DETAIL = "This content belongs to a different course."


def _scoped_course(request: Request) -> Course:
    """The course this request was launched into.

    From the session, never from the request (D-043). `CourseScoped` has
    already established that a scope exists; this turns it into a row.
    """
    scope = launch_scope(request)
    if scope is None:
        # Unreachable while CourseScoped is in permission_classes. Kept for the
        # same reason LaunchContextView keeps its equivalent: a later edit to
        # that tuple must not be able to turn this into a 500.
        raise PermissionDenied("This request did not arrive from a Canvas launch.")

    course = get_course(scope.course_id)
    if course is None:
        logger.warning("Launch scope names course %s, which no longer exists.", scope.course_id)
        raise NotFound("That course is no longer available.")
    return course


def _readable_book(request: Request) -> Book:
    """The one book this launch may read, or a refusal explaining why not."""
    resolution = book_for_course(_scoped_course(request))
    if resolution.book is None:
        raise NotFound(UNAVAILABLE_DETAIL[resolution.availability])
    return resolution.book


def _book_or_refuse(request: Request, book_id: UUID) -> Book:
    """The launch's book, having confirmed it is the one being asked for.

    The cross-course refusal, and the only place a book id from a URL is
    consulted at all. The comparison is one way round on purpose: the course
    decides which book it opens, and the request may only name it.
    """
    book = _readable_book(request)
    if book.pk != book_id:
        raise PermissionDenied(WRONG_COURSE_DETAIL)
    return book


def _published_order(book: Book) -> list[ContentNode]:
    """The book's reading order, with unpublished nodes removed.

    Two queries, and the single point where rule C.9 is enforced for
    navigation (D-055). Everything else — the contents, the breadcrumb,
    previous and next — is derived from this one list in memory.
    """
    order = reading_order(book)
    published = published_node_ids(order)
    return [node for node in order if node.pk in published]


def _toc_entry(entry: TocEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "title": entry.title,
        "node_type": entry.node_type,
        "depth": entry.depth,
        "children": [_toc_entry(child) for child in entry.children],
    }


def _book_summary(book: Book) -> dict[str, Any]:
    return {
        "id": str(book.pk),
        "title": book.title,
        "slug": book.slug,
        "description": book.description,
    }


def _node_link(node: ContentNode | None) -> dict[str, Any] | None:
    """A node as somewhere to go — the shape of a breadcrumb or a prev/next."""
    if node is None:
        return None
    return {"id": str(node.pk), "title": node.title, "node_type": node.node_type}


def _breadcrumb(node: ContentNode, order: list[ContentNode]) -> list[ContentNode]:
    """The node's ancestors, outermost first, as far as they are published.

    Derived from the order the caller already holds rather than queried, which
    is the same reasoning D-055 gives for `neighbours` — and here it also makes
    the breadcrumb obey the publication gate for free. An unpublished chapter
    is absent from the order, so a published section under it shows a shorter
    trail rather than naming a chapter the student cannot open.

    Every ancestor's path is a prefix of this node's (D-054), so this is a set
    membership test and not a tree walk.
    """
    ancestors = set(node.ancestor_paths)
    return [candidate for candidate in order if candidate.path in ancestors]


class TextbookView(APIView):
    """Which textbook this launch opens.

    The reader's first call: it has a session and a course, and needs a book id
    before it can ask for anything else. It also carries the distinction D-057
    preserved — no textbook linked, versus one not yet published — which is the
    difference between the reader telling a student to ask their instructor and
    telling them to wait.
    """

    permission_classes = (IsAuthenticated, CourseScoped)

    def get(self, request: Request) -> Response:
        resolution = book_for_course(_scoped_course(request))
        return Response(
            {
                "availability": resolution.availability.value,
                "book": _book_summary(resolution.book) if resolution.book else None,
            }
        )


class BookTocView(APIView):
    """A book's table of contents, published parts only."""

    permission_classes = (IsAuthenticated, CourseScoped)

    def get(self, request: Request, book_id: UUID) -> Response:
        book = _book_or_refuse(request, book_id)
        return Response(
            {
                "book": _book_summary(book),
                "toc": [_toc_entry(entry) for entry in nest(_published_order(book))],
            }
        )


class NodeView(APIView):
    """One node's published body, with its place in the book around it."""

    permission_classes = (IsAuthenticated, CourseScoped)

    def get(self, request: Request, node_id: UUID) -> Response:
        node = ContentNode.objects.filter(pk=node_id).first()
        if node is None:
            raise NotFound("No such content.")

        # Refused by name rather than hidden as a 404: a reader who followed a
        # stale link from another course should be told what happened, and
        # this is the refusal acceptance criterion 12 asks to see.
        book = _readable_book(request)
        if node.book_id != book.pk:
            raise PermissionDenied(WRONG_COURSE_DETAIL)

        order = _published_order(book)
        if not any(candidate.pk == node.pk for candidate in order):
            # In this book, and readable in principle, but nothing of it is
            # published. Not a refusal — there is simply nothing to read yet.
            raise NotFound("That part of the textbook has not been published yet.")

        version = published_version(node)
        if version is None:  # pragma: no cover - the order was built from this
            raise NotFound("That part of the textbook has not been published yet.")

        around = neighbours(node, order)
        return Response(
            {
                "id": str(node.pk),
                "title": node.title,
                "node_type": node.node_type,
                "book_id": str(book.pk),
                "breadcrumb": [_node_link(step) for step in _breadcrumb(node, order)],
                "body": version.body,
                # Which version produced this text. When a reader reports that
                # a paragraph is wrong, this is the difference between a
                # five-minute fix and archaeology.
                "version_number": version.version_number,
                "previous": _node_link(around.previous),
                "next": _node_link(around.next),
            }
        )
