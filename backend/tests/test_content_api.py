"""The read API, and the first cross-course refusal this platform can produce.

D-044 recorded that acceptance criterion 12 rested on nothing: the permission's
object half had no caller, so no request could be refused for belonging to
another course. `TestCrossCourseRefusal` below is that gap closed.

The rest is D-053's two gates, seen from the outside. A student reaches a node
when the book is published *and* the node has a published version, and the
navigation derived from that — contents, breadcrumb, previous and next — is
filtered once, in one place (D-055), so the Next button cannot walk into a
draft.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.content.models import Book, BookStatus, ContentNode, NodeType
from apps.courses.services import Course, Role, link_course_to_book
from services.launch_session import SESSION_COURSE_KEY, SESSION_ROLE_KEY
from tests.factories import (
    BookFactory,
    ContentNodeFactory,
    ContentVersionFactory,
    CourseFactory,
    UserFactory,
    tiptap_document,
)

pytestmark = pytest.mark.django_db


def toc_url(book: Book) -> str:
    return reverse("content:book-toc", args=[book.pk])


def node_url(node: ContentNode) -> str:
    return reverse("content:node", args=[node.pk])


# Routes are reversed inside tests, never at import: `reverse` at module level
# runs before pytest-django has finished setting Django up.
ROUTE_NAMES = ("content:textbook", "content:book-toc", "content:node")


def textbook_url() -> str:
    return reverse("content:textbook")


def url_for(route: str) -> str:
    """Any URL for a route, for tests that only care that it is refused."""
    if route == "content:textbook":
        return reverse(route)
    return reverse(route, args=[uuid.uuid4()])


def publish(node: ContentNode, *paragraphs: str) -> None:
    """Give a node a published version, as task 3.6's publish will."""
    ContentVersionFactory(
        node=node, body=tiptap_document(*(paragraphs or ("Text.",))), is_published=True
    )


def build_book(*, published: bool = True) -> tuple[Book, dict[str, ContentNode]]:
    """A small book: one unit, two chapters, two sections under the first.

    Every node is published. Tests that care about the unpublished case
    withhold one deliberately, so what is being tested is visible in the test
    rather than buried in this helper.
    """
    book = BookFactory(status=BookStatus.PUBLISHED if published else BookStatus.DRAFT)
    unit = ContentNodeFactory(book=book, node_type=NodeType.UNIT, title="Unit One", position=1)
    chapter = ContentNodeFactory(
        book=book, parent=unit, node_type=NodeType.CHAPTER, title="Chapter One", position=1
    )
    first = ContentNodeFactory(
        book=book, parent=chapter, node_type=NodeType.SECTION, title="Section One", position=1
    )
    second = ContentNodeFactory(
        book=book, parent=chapter, node_type=NodeType.SECTION, title="Section Two", position=2
    )
    last = ContentNodeFactory(
        book=book, parent=unit, node_type=NodeType.CHAPTER, title="Chapter Two", position=2
    )
    nodes = {"unit": unit, "chapter": chapter, "first": first, "second": second, "last": last}
    for node in nodes.values():
        publish(node)
    return book, nodes


def course_opening(book: Book) -> Course:
    course = CourseFactory()
    link_course_to_book(course, book)
    return course


def queries_to_read(url_of: Callable[[Book], str], *, chapters: int) -> int:
    """How many queries one request costs against a book of a given size."""
    book = BookFactory(status=BookStatus.PUBLISHED)
    unit = ContentNodeFactory(book=book, node_type=NodeType.UNIT, position=1)
    publish(unit)
    for position in range(1, chapters + 1):
        chapter = ContentNodeFactory(
            book=book, parent=unit, node_type=NodeType.CHAPTER, position=position
        )
        publish(chapter)

    course = CourseFactory()
    link_course_to_book(course, book)
    client = Client()
    client.force_login(UserFactory())
    session = client.session
    session[SESSION_COURSE_KEY] = str(course.pk)
    session[SESSION_ROLE_KEY] = Role.STUDENT.value
    session.save()

    with CaptureQueriesContext(connection) as captured:
        assert client.get(url_of(book)).status_code == 200
    return len(captured)


class TestTheEndpointsRequireALaunch:
    @pytest.mark.parametrize("route", ROUTE_NAMES)
    def test_an_anonymous_request_is_refused(self, client: Client, route: str) -> None:
        """Default deny (D-012), on every route this module mounts."""
        assert client.get(url_for(route)).status_code == 403

    @pytest.mark.parametrize("route", ROUTE_NAMES)
    def test_a_signed_in_user_with_no_launch_is_refused(self, route: str) -> None:
        """An operator logged into the Django admin has a real session and is
        authenticated, and still reaches nothing: it is the course key that
        gates this, not the user (D-044)."""
        client = Client()
        client.force_login(UserFactory())
        assert client.get(url_for(route)).status_code == 403


class TestWhichTextbookACourseOpens:
    def test_it_names_the_course_book(self, launch_as: Callable[..., Client]) -> None:
        book, _ = build_book()
        response = launch_as(course_opening(book)).get(textbook_url())
        assert response.status_code == 200
        assert response.json()["availability"] == "AVAILABLE"
        assert response.json()["book"]["id"] == str(book.pk)

    def test_a_course_with_no_textbook_says_so(self, launch_as: Callable[..., Client]) -> None:
        """Distinguished from an unpublished one because the fix differs: this
        one needs an administrator to link a book (D-057)."""
        response = launch_as(CourseFactory()).get(textbook_url())
        assert response.status_code == 200
        assert response.json() == {"availability": "NO_BOOK_LINKED", "book": None}

    def test_an_unpublished_textbook_is_named_as_such_and_withheld(
        self, launch_as: Callable[..., Client]
    ) -> None:
        book, _ = build_book(published=False)
        response = launch_as(course_opening(book)).get(textbook_url())
        assert response.json()["availability"] == "BOOK_NOT_PUBLISHED"
        assert response.json()["book"] is None


class TestTableOfContents:
    def test_it_returns_the_book_tree_nested(self, launch_as: Callable[..., Client]) -> None:
        book, nodes = build_book()
        response = launch_as(course_opening(book)).get(toc_url(book))
        assert response.status_code == 200

        toc = response.json()["toc"]
        assert [entry["title"] for entry in toc] == ["Unit One"]
        assert [entry["title"] for entry in toc[0]["children"]] == ["Chapter One", "Chapter Two"]
        assert [entry["title"] for entry in toc[0]["children"][0]["children"]] == [
            "Section One",
            "Section Two",
        ]
        assert toc[0]["id"] == str(nodes["unit"].pk)

    def test_an_unpublished_node_is_absent(self, launch_as: Callable[..., Client]) -> None:
        """Rule C.9. A chapter an editor is still writing is not listed at
        all — a student cannot see that it exists."""
        book, nodes = build_book()
        nodes["second"].versions.update(is_published=False)

        toc = launch_as(course_opening(book)).get(toc_url(book)).json()["toc"]
        titles = [c["title"] for c in toc[0]["children"][0]["children"]]
        assert titles == ["Section One"]

    def test_a_book_with_nothing_published_returns_an_empty_contents(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """The book is published, its chapters are not. An empty contents, not
        an error: the reader shows "nothing here yet" rather than breaking."""
        book = BookFactory(status=BookStatus.PUBLISHED)
        ContentNodeFactory(book=book)
        response = launch_as(course_opening(book)).get(toc_url(book))
        assert response.status_code == 200
        assert response.json()["toc"] == []

    def test_a_course_with_no_textbook_is_told_so(self, launch_as: Callable[..., Client]) -> None:
        book, _ = build_book()
        response = launch_as(CourseFactory()).get(toc_url(book))
        assert response.status_code == 404

    def test_its_cost_does_not_grow_with_the_size_of_the_book(self) -> None:
        """The property that matters, asserted instead of a magic number: a
        book with forty chapters costs exactly what a book with five costs.
        That is what the sortable path (D-054) and the single read (D-055) buy,
        and a regression to a query per node would be invisible otherwise."""
        assert queries_to_read(toc_url, chapters=2) == queries_to_read(toc_url, chapters=40)


class TestReadingANode:
    def test_it_returns_the_published_body(self, launch_as: Callable[..., Client]) -> None:
        book, nodes = build_book()
        # Withdraw before publishing the next one: the partial unique index
        # cannot be deferred, so the other order violates it mid-transaction.
        nodes["first"].versions.filter(version_number=1).update(is_published=False)
        publish(nodes["first"], "The published wording.")

        response = launch_as(course_opening(book)).get(node_url(nodes["first"]))
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Section One"
        assert body["body"]["content"][0]["content"][0]["text"] == "The published wording."
        assert body["version_number"] == 2

    def test_it_carries_the_breadcrumb_outermost_first(
        self, launch_as: Callable[..., Client]
    ) -> None:
        book, nodes = build_book()
        response = launch_as(course_opening(book)).get(node_url(nodes["first"]))
        assert [step["title"] for step in response.json()["breadcrumb"]] == [
            "Unit One",
            "Chapter One",
        ]

    def test_previous_and_next_cross_a_chapter_boundary(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """The whole point of the materialised path (D-054): the last section
        of one chapter is followed by the next chapter, with no special case."""
        book, nodes = build_book()
        response = launch_as(course_opening(book)).get(node_url(nodes["second"]))
        assert response.json()["previous"]["title"] == "Section One"
        assert response.json()["next"]["title"] == "Chapter Two"

    def test_the_first_node_has_no_previous_and_the_last_no_next(
        self, launch_as: Callable[..., Client]
    ) -> None:
        book, nodes = build_book()
        client = launch_as(course_opening(book))
        assert client.get(node_url(nodes["unit"])).json()["previous"] is None
        assert client.get(node_url(nodes["last"])).json()["next"] is None

    def test_next_skips_an_unpublished_node_rather_than_landing_on_it(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """The failure D-055 exists to prevent. The filter is applied once, to
        the reading order, so a draft has no neighbours rather than wrong
        ones — and Next steps over it."""
        book, nodes = build_book()
        nodes["second"].versions.update(is_published=False)

        response = launch_as(course_opening(book)).get(node_url(nodes["first"]))
        assert response.json()["next"]["title"] == "Chapter Two"

    def test_an_unpublished_node_is_not_readable(self, launch_as: Callable[..., Client]) -> None:
        book, nodes = build_book()
        nodes["second"].versions.update(is_published=False)
        response = launch_as(course_opening(book)).get(node_url(nodes["second"]))
        assert response.status_code == 404

    def test_a_node_that_does_not_exist_is_not_found(
        self, launch_as: Callable[..., Client]
    ) -> None:
        book, _ = build_book()
        missing = ContentNodeFactory.build(book=book)
        response = launch_as(course_opening(book)).get(reverse("content:node", args=[missing.pk]))
        assert response.status_code == 404

    def test_a_breadcrumb_skips_an_unpublished_ancestor(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """A shorter trail rather than naming a chapter the student cannot
        open."""
        book, nodes = build_book()
        nodes["chapter"].versions.update(is_published=False)

        response = launch_as(course_opening(book)).get(node_url(nodes["first"]))
        assert [step["title"] for step in response.json()["breadcrumb"]] == ["Unit One"]

    def test_its_cost_does_not_grow_with_the_size_of_the_book(self) -> None:
        """Same invariant, and one more thing: reading one node must not load
        every chapter's body. `published_node_ids` did exactly that until this
        task was written, and nothing would have noticed — the responses were
        identical, only the cost was not."""

        def first_node_url(book: Book) -> str:
            return node_url(book.nodes.order_by("path")[1])

        assert queries_to_read(first_node_url, chapters=2) == queries_to_read(
            first_node_url, chapters=40
        )


class TestCrossCourseRefusal:
    """Acceptance criterion 12, demonstrable for the first time (D-044)."""

    def test_a_reader_cannot_open_another_courses_book(
        self, launch_as: Callable[..., Client]
    ) -> None:
        mine, _ = build_book()
        theirs, _ = build_book()
        course_opening(theirs)

        response = launch_as(course_opening(mine)).get(toc_url(theirs))
        assert response.status_code == 403
        assert response.json()["detail"] == "This content belongs to a different course."

    def test_a_reader_cannot_open_a_node_from_another_courses_book(
        self, launch_as: Callable[..., Client]
    ) -> None:
        mine, _ = build_book()
        theirs, their_nodes = build_book()
        course_opening(theirs)

        response = launch_as(course_opening(mine)).get(node_url(their_nodes["first"]))
        assert response.status_code == 403
        assert response.json()["detail"] == "This content belongs to a different course."

    def test_a_book_id_in_the_url_cannot_widen_what_is_reachable(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """The scope comes from the session, never the request (D-043). A book
        id is only ever checked against what the course opens."""
        mine, _ = build_book()
        unlinked = BookFactory(status=BookStatus.PUBLISHED)

        response = launch_as(course_opening(mine)).get(toc_url(unlinked))
        assert response.status_code == 403

    def test_refusal_does_not_reveal_whether_the_book_exists(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """A real book from another course and an id that is nothing at all
        must answer identically, or the endpoint is an oracle."""
        mine, _ = build_book()
        theirs, _ = build_book()
        client = launch_as(course_opening(mine))

        real = client.get(toc_url(theirs))
        invented = client.get(reverse("content:book-toc", args=[BookFactory.build().pk]))
        assert real.status_code == invented.status_code == 403
        assert real.json() == invented.json()

    def test_two_courses_sharing_one_textbook_may_both_read_it(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """The ordinary case, and the one a careless scope check would break:
        several sections of a course, one nursing textbook."""
        book, nodes = build_book()
        for _ in range(2):
            client = launch_as(course_opening(book))
            assert client.get(toc_url(book)).status_code == 200
            assert client.get(node_url(nodes["first"])).status_code == 200

    def test_a_faculty_launch_is_scoped_exactly_as_a_student_launch(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """Role decides the route, not access (D-046). A teacher in course A
        has no more reach into course B than a student does."""
        mine, _ = build_book()
        theirs, _ = build_book()
        course_opening(theirs)

        client = launch_as(course_opening(mine), role=Role.FACULTY)
        assert client.get(toc_url(theirs)).status_code == 403

    def test_withdrawing_a_book_takes_effect_on_the_next_request(
        self, launch_as: Callable[..., Client]
    ) -> None:
        """The session is not a cache of what may be read. Archiving a book
        closes it to a reader already holding a launched session."""
        book, nodes = build_book()
        client = launch_as(course_opening(book))
        assert client.get(node_url(nodes["first"])).status_code == 200

        book.status = BookStatus.ARCHIVED
        book.save(update_fields=["status", "updated_at"])
        assert client.get(node_url(nodes["first"])).status_code == 404
