"""Books.

The outer of the two gates that decide whether a student sees anything: a book
must be published, and within it each node shows only its published version
(task 2.4).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.content.models import Book, BookStatus, ContentNode, NodeType
from tests.factories import BookFactory, ContentNodeFactory

pytestmark = pytest.mark.django_db


class TestBookIdentity:
    def test_the_identifier_is_a_uuid_not_a_sequence(self) -> None:
        """Rule C.2. Everything that points at content — course mappings,
        search documents, reading positions — stores this."""
        assert isinstance(BookFactory().pk, uuid.UUID)

    def test_a_slug_is_unique(self) -> None:
        BookFactory(slug="nursing-fundamentals")
        with pytest.raises(IntegrityError), transaction.atomic():
            BookFactory.create(slug="nursing-fundamentals", title="Another")

    def test_renaming_a_slug_does_not_change_identity(self) -> None:
        """A slug is a handle, never a reference. If anything stored one, a
        rename would silently move every reading position in the book."""
        book = BookFactory(slug="before")
        original = book.pk
        book.slug = "after"
        book.save(update_fields=["slug", "updated_at"])
        book.refresh_from_db()
        assert book.pk == original

    def test_a_book_cannot_be_created_without_a_title(self) -> None:
        """Enforced by the database, not only by a form: an untitled book is
        unfindable in a CMS list and unnameable in a course."""
        with pytest.raises(IntegrityError), transaction.atomic():
            Book.objects.create(title="", slug="untitled")


class TestReadability:
    def test_a_new_book_is_a_draft(self) -> None:
        """The safe default. A book created by an import (task 3.11) must not
        become visible because someone forgot a step."""
        assert BookFactory().status == BookStatus.DRAFT
        assert BookFactory().is_readable is False

    def test_only_a_published_book_is_readable(self) -> None:
        assert BookFactory(status=BookStatus.PUBLISHED).is_readable is True

    def test_an_archived_book_is_not_readable_and_is_not_deleted(self) -> None:
        """Withdrawing a book keeps its versions and the reading positions that
        point into it, so re-publishing restores everything."""
        book = BookFactory(status=BookStatus.PUBLISHED)
        book.status = BookStatus.ARCHIVED
        book.save(update_fields=["status", "updated_at"])

        assert book.is_readable is False
        assert Book.objects.filter(pk=book.pk).exists()

    @pytest.mark.parametrize("status", list(BookStatus))
    def test_exactly_one_status_is_readable(self, status: BookStatus) -> None:
        book = BookFactory(status=status)
        assert book.is_readable is (status == BookStatus.PUBLISHED)


def test_books_are_listed_in_a_stable_order() -> None:
    """A CMS list that reorders itself between page loads is unusable."""
    BookFactory(title="Zoology", slug="z")
    BookFactory(title="Anatomy", slug="a")
    assert [book.title for book in Book.objects.all()] == ["Anatomy", "Zoology"]


class TestTheMaterialisedPath:
    """The path is what makes the table of contents one query instead of one
    per level. These assert the properties task 2.3 will rely on."""

    def test_text_order_matches_reading_order(self) -> None:
        """Zero padding is the whole reason: "10" sorts before "2" unpadded,
        which would put section 10 before section 2 in every table of contents.
        """
        assert ContentNode.build_path("0001", 2) < ContentNode.build_path("0001", 10)

    def test_a_parent_sorts_before_its_own_children(self) -> None:
        chapter = ContentNode.build_path("0001", 1)
        assert chapter < ContentNode.build_path(chapter, 1)

    def test_crossing_a_parent_boundary_needs_no_special_case(self) -> None:
        """The last section of chapter one precedes chapter two, so "next" is
        simply the following row — which is what task 2.3's prev/next depends on.
        """
        chapter_one = ContentNode.build_path("0001", 1)
        last_section = ContentNode.build_path(chapter_one, 99)
        chapter_two = ContentNode.build_path("0001", 2)
        assert last_section < chapter_two

    def test_a_subtree_prefix_matches_only_descendants(self) -> None:
        chapter_one = ContentNode.build_path("0001", 1)
        assert ContentNode.build_path(chapter_one, 1).startswith(f"{chapter_one}.")
        assert not ContentNode.build_path("0001", 2).startswith(f"{chapter_one}.")

    def test_a_top_level_node_has_no_leading_separator(self) -> None:
        assert ContentNode.build_path("", 1) == "0001"

    @pytest.mark.django_db
    def test_ancestors_are_the_paths_prefixes(self) -> None:
        """Resolving a breadcrumb is one IN query, not one query per level."""
        unit = ContentNodeFactory(position=1)
        chapter = ContentNodeFactory(book=unit.book, parent=unit, position=3)
        section = ContentNodeFactory(book=unit.book, parent=chapter, position=2)

        assert section.path == "0001.0003.0002"
        assert section.ancestor_paths == [unit.path, chapter.path]
        assert unit.ancestor_paths == []

    @pytest.mark.django_db
    def test_depth_counts_levels_from_one(self) -> None:
        unit = ContentNodeFactory(position=1)
        chapter = ContentNodeFactory(book=unit.book, parent=unit, position=1)
        assert (unit.depth, chapter.depth) == (1, 2)


@pytest.mark.django_db
class TestTheTreeReadsInOrder:
    def test_a_whole_book_comes_back_in_reading_order(self) -> None:
        book = BookFactory()
        unit = ContentNodeFactory(book=book, position=1)
        chapter_two = ContentNodeFactory(book=book, parent=unit, position=2)
        chapter_one = ContentNodeFactory(book=book, parent=unit, position=1)
        section = ContentNodeFactory(book=book, parent=chapter_one, position=1)

        assert list(ContentNode.objects.filter(book=book)) == [
            unit,
            chapter_one,
            section,
            chapter_two,
        ]

    def test_a_node_cannot_be_created_without_a_title(self) -> None:
        book = BookFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            ContentNode.objects.create(book=book, node_type=NodeType.UNIT, title="", path="0001")

    def test_a_node_cannot_be_created_without_a_path(self) -> None:
        """A node outside the path ordering is invisible to every tree read."""
        book = BookFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            ContentNode.objects.create(book=book, node_type=NodeType.UNIT, title="Unit", path="")

    def test_a_book_with_nodes_cannot_be_deleted(self) -> None:
        """PROTECT, so a stray delete fails loudly rather than quietly taking a
        subtree and every reading position in it."""
        from django.db.models import ProtectedError

        node = ContentNodeFactory()
        with pytest.raises(ProtectedError), transaction.atomic():
            node.book.delete()
