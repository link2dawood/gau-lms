"""Which textbook a launched course opens.

The outer of D-053's two gates, and the join between a Canvas course and the
content the platform serves. Two things are protected here: that the question
"which book does this course open" has exactly one answer, and that an
unpublished book is not that answer.

Task 2.6 consumes this. Acceptance criteria 4 and 5 rest on it — a launch that
resolves to no book is a reader with nothing to show.
"""

from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.content.models import BookStatus
from apps.courses.models import Course, CourseBook
from apps.courses.services import active_book_link, find_course, link_course_to_book
from services.course_books import BookAvailability, book_for_course
from tests.factories import ISSUER, PLATFORM_GUID, BookFactory, CourseBookFactory, CourseFactory

pytestmark = pytest.mark.django_db


class TestTheMapping:
    def test_the_identifier_is_a_uuid_not_a_sequence(self) -> None:
        assert isinstance(CourseBookFactory().pk, uuid.UUID)

    def test_a_course_opens_the_book_it_is_linked_to(self) -> None:
        link = CourseBookFactory()
        assert active_book_link(link.course) == link

    def test_a_course_with_no_mapping_has_no_link(self) -> None:
        assert active_book_link(CourseFactory()) is None

    def test_a_course_cannot_have_two_active_books(self) -> None:
        """Without this the reader's behaviour would depend on row order.
        Enforced by a partial unique index, not by the service."""
        course = CourseFactory()
        CourseBookFactory(course=course, is_active=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            CourseBookFactory(course=course, is_active=True)

    def test_a_course_and_a_book_are_related_at_most_once(self) -> None:
        """So that moving a course back to a previous textbook reactivates the
        row it had rather than accumulating duplicates that say the same
        thing."""
        course, book = CourseFactory(), BookFactory()
        CourseBookFactory(course=course, book=book, is_active=False)
        with pytest.raises(IntegrityError), transaction.atomic():
            CourseBookFactory(course=course, book=book, is_active=True)

    def test_one_book_may_serve_many_courses(self) -> None:
        """The ordinary case: one nursing textbook, every section of the
        course using it."""
        book = BookFactory()
        for _ in range(3):
            CourseBookFactory(course=CourseFactory(), book=book)
        assert CourseBook.objects.filter(book=book, is_active=True).count() == 3

    def test_a_course_keeps_the_mappings_it_has_retired(self) -> None:
        """Which book a course opened last term is a real question, and a
        reading position was formed under that mapping."""
        course = CourseFactory()
        CourseBookFactory(course=course, is_active=False)
        CourseBookFactory(course=course, is_active=True)
        assert CourseBook.objects.filter(course=course).count() == 2


class TestLinking:
    def test_linking_a_course_to_a_book_makes_it_the_active_one(self) -> None:
        course, book = CourseFactory(), BookFactory()
        link = link_course_to_book(course, book)
        assert active_book_link(course) == link
        assert link.is_active is True

    def test_relinking_retires_the_previous_book_rather_than_deleting_it(self) -> None:
        """Deactivate first, then activate — the order the partial unique index
        forces, since it cannot be deferred in PostgreSQL."""
        course = CourseFactory()
        first, second = BookFactory(), BookFactory()
        old = link_course_to_book(course, first)
        new = link_course_to_book(course, second)

        old.refresh_from_db()
        assert old.is_active is False
        assert active_book_link(course) == new
        assert CourseBook.objects.filter(course=course).count() == 2

    def test_relinking_to_a_previous_book_reuses_its_row(self) -> None:
        """Reversible without accumulating rows."""
        course = CourseFactory()
        first, second = BookFactory(), BookFactory()
        original = link_course_to_book(course, first)
        link_course_to_book(course, second)
        restored = link_course_to_book(course, first)

        assert restored.pk == original.pk
        assert CourseBook.objects.filter(course=course).count() == 2

    def test_linking_is_idempotent(self) -> None:
        course, book = CourseFactory(), BookFactory()
        first = link_course_to_book(course, book)
        assert link_course_to_book(course, book).pk == first.pk
        assert CourseBook.objects.filter(course=course).count() == 1

    def test_linking_does_not_touch_another_course(self) -> None:
        """The deactivation is scoped to one course. A sweep that was not
        would silently unlink every other course from its textbook."""
        mine, theirs = CourseFactory(), CourseFactory()
        theirs_link = CourseBookFactory(course=theirs)
        link_course_to_book(mine, BookFactory())

        theirs_link.refresh_from_db()
        assert theirs_link.is_active is True


class TestResolvingWhatACourseOpens:
    def test_a_published_book_is_available(self) -> None:
        link = CourseBookFactory(book=BookFactory(status=BookStatus.PUBLISHED))
        result = book_for_course(link.course)
        assert result.availability is BookAvailability.AVAILABLE
        assert result.is_available is True
        assert result.book == link.book

    def test_a_course_with_no_book_says_so(self) -> None:
        """Distinguished from an unpublished book on purpose: the fix is an
        administrator linking a textbook, not publishing one."""
        result = book_for_course(CourseFactory())
        assert result.availability is BookAvailability.NO_BOOK_LINKED
        assert result.book is None

    @pytest.mark.parametrize("status", [BookStatus.DRAFT, BookStatus.ARCHIVED])
    def test_an_unpublished_book_is_refused_and_not_carried(self, status: str) -> None:
        """The book is withheld, not merely flagged. A caller that ignores
        `availability` gets nothing rather than a draft textbook — the right
        way round to be wrong."""
        link = CourseBookFactory(book=BookFactory(status=status))
        result = book_for_course(link.course)
        assert result.availability is BookAvailability.BOOK_NOT_PUBLISHED
        assert result.is_available is False
        assert result.book is None

    def test_a_retired_mapping_does_not_resolve(self) -> None:
        """Withdrawing a textbook takes effect immediately, even though the row
        stays."""
        link = CourseBookFactory(book=BookFactory(status=BookStatus.PUBLISHED), is_active=False)
        assert book_for_course(link.course).availability is BookAvailability.NO_BOOK_LINKED

    def test_publishing_a_linked_book_makes_it_available(self) -> None:
        """The mapping and the publication are independent gates; neither
        implies the other."""
        link = CourseBookFactory(book=BookFactory(status=BookStatus.DRAFT))
        assert book_for_course(link.course).is_available is False

        link.book.status = BookStatus.PUBLISHED
        link.book.save(update_fields=["status", "updated_at"])
        assert book_for_course(link.course).is_available is True

    def test_archiving_a_book_withdraws_it_from_every_course(self) -> None:
        """One book, several courses, one withdrawal. Nothing is deleted and
        the mappings survive, so re-publishing restores the lot (D-053)."""
        book = BookFactory(status=BookStatus.PUBLISHED)
        courses = [CourseBookFactory(book=book).course for _ in range(3)]
        assert all(book_for_course(c).is_available for c in courses)

        book.status = BookStatus.ARCHIVED
        book.save(update_fields=["status", "updated_at"])
        assert not any(book_for_course(c).is_available for c in courses)
        assert CourseBook.objects.filter(book=book, is_active=True).count() == 3

    def test_it_costs_one_query(self, django_assert_num_queries: object) -> None:
        """A launch resolves its textbook on the way to the reader, so this is
        on the critical path of every page load. `select_related` is what keeps
        the book from being a second round trip."""
        link = CourseBookFactory(book=BookFactory(status=BookStatus.PUBLISHED))
        with django_assert_num_queries(1):  # type: ignore[operator]
            assert book_for_course(link.course).is_available


class TestNothingIsDeleted:
    def test_a_book_a_course_points_at_cannot_be_deleted(self) -> None:
        link = CourseBookFactory()
        with pytest.raises(ProtectedError), transaction.atomic():
            link.book.delete()

    def test_a_course_with_a_mapping_cannot_be_deleted(self) -> None:
        link = CourseBookFactory()
        with pytest.raises(ProtectedError), transaction.atomic():
            link.course.delete()


class TestFindingACourseWithoutCreatingOne:
    """`find_course` exists so that asking a question cannot create a row.

    The deep linking title is the caller: answering "which book does this
    course open" must not bring a course into existence as a side effect,
    because a deep linking request is answered before provisioning (D-050).
    """

    def test_it_finds_a_course_by_its_canvas_identity(self) -> None:
        course = CourseFactory()
        assert (
            find_course(
                issuer=course.issuer,
                platform_guid=course.platform_guid,
                canvas_course_id=course.canvas_course_id,
            )
            == course
        )

    def test_it_returns_none_for_a_course_never_launched(self) -> None:
        assert (
            find_course(issuer=ISSUER, platform_guid=PLATFORM_GUID, canvas_course_id="99999")
            is None
        )

    def test_it_creates_nothing(self, django_assert_num_queries: object) -> None:
        with django_assert_num_queries(1):  # type: ignore[operator]
            find_course(issuer=ISSUER, platform_guid=PLATFORM_GUID, canvas_course_id="99999")
        assert not Course.objects.filter(canvas_course_id="99999").exists()

    def test_it_does_not_cross_platform_instances(self) -> None:
        """The D-032 identity in full. Two Instructure-hosted Canvases share an
        issuer, so the guid is what keeps one university's course 42 from
        resolving to another's."""
        course = CourseFactory(canvas_course_id="42", platform_guid="one.instructure.com")
        assert (
            find_course(
                issuer=course.issuer,
                platform_guid="two.instructure.com",
                canvas_course_id="42",
            )
            is None
        )

    def test_an_empty_canvas_course_id_finds_nothing(self) -> None:
        """An account-level deep linking request carries no context id. It must
        resolve to nothing rather than to whichever course happens to have a
        blank one."""
        assert find_course(issuer=ISSUER, platform_guid=PLATFORM_GUID, canvas_course_id="") is None
