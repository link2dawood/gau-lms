"""The tree service — the four reads the reader depends on.

Nesting and neighbours are pure functions over a path-ordered list, so most of
this runs without a database. That is deliberate: the expensive part of a tree
is the query, and the query is one `ORDER BY path`.
"""

from __future__ import annotations

import pytest

from apps.content.services import (
    Neighbours,
    ancestors_of,
    neighbours,
    nest,
    reading_order,
    table_of_contents,
)
from tests.factories import BookFactory, ContentNodeFactory


class FlatNode:
    """The shape `nest` and `neighbours` actually need, without a database."""

    def __init__(self, pk: str, title: str, node_type: str, depth: int) -> None:
        self.pk = pk
        self.title = title
        self.node_type = node_type
        self.depth = depth


def sample_book() -> list[FlatNode]:
    return [
        FlatNode("u1", "Cardiovascular System", "UNIT", 1),
        FlatNode("c1", "Blood Pressure", "CHAPTER", 2),
        FlatNode("s1", "Measuring BP", "SECTION", 3),
        FlatNode("s2", "Classification", "SECTION", 3),
        FlatNode("c2", "Heart Failure", "CHAPTER", 2),
        FlatNode("u2", "Respiratory System", "UNIT", 1),
    ]


class TestNesting:
    def test_a_flat_ordered_list_becomes_a_tree(self) -> None:
        toc = nest(sample_book())  # type: ignore[arg-type]
        assert [entry.title for entry in toc] == [
            "Cardiovascular System",
            "Respiratory System",
        ]
        assert [entry.title for entry in toc[0].children] == ["Blood Pressure", "Heart Failure"]
        assert [entry.title for entry in toc[0].children[0].children] == [
            "Measuring BP",
            "Classification",
        ]

    def test_an_empty_book_nests_to_nothing(self) -> None:
        assert nest([]) == []

    def test_a_node_whose_parent_is_missing_still_appears(self) -> None:
        """Imports produce irregular trees (task 3.13). A chapter silently
        absent from the contents is worse than one shown a level too high."""
        irregular = [
            FlatNode("u1", "Unit", "UNIT", 1),
            FlatNode("s1", "Orphaned section", "SECTION", 3),
        ]
        toc = nest(irregular)  # type: ignore[arg-type]
        assert len(toc) == 1
        assert [entry.title for entry in toc[0].children] == ["Orphaned section"]

    def test_nesting_does_not_depend_on_parent_ids(self) -> None:
        """Depth decides nesting, so a filtered reading order — published-only,
        in task 2.6 — nests without a second pass."""
        published_only = [n for n in sample_book() if n.pk != "c1"]
        toc = nest(published_only)  # type: ignore[arg-type]
        assert [entry.title for entry in toc[0].children] == [
            "Measuring BP",
            "Classification",
            "Heart Failure",
        ]


class TestNeighbours:
    def test_the_last_section_leads_into_the_next_chapter(self) -> None:
        """The boundary case the materialised path exists to make ordinary."""
        book = sample_book()
        assert neighbours(book[3], book).next is book[4]  # type: ignore[arg-type]

    def test_the_last_chapter_leads_into_the_next_unit(self) -> None:
        book = sample_book()
        assert neighbours(book[4], book).next is book[5]  # type: ignore[arg-type]

    def test_a_child_follows_its_own_parent(self) -> None:
        book = sample_book()
        assert neighbours(book[0], book).next is book[1]  # type: ignore[arg-type]

    def test_the_first_and_last_nodes_have_one_side_only(self) -> None:
        book = sample_book()
        assert neighbours(book[0], book).previous is None  # type: ignore[arg-type]
        assert neighbours(book[-1], book).next is None  # type: ignore[arg-type]

    def test_a_node_outside_the_order_has_no_neighbours(self) -> None:
        """Rather than the wrong ones. A node the caller filtered out —
        unpublished, say — must not be navigable to."""
        book = sample_book()
        absent = FlatNode("gone", "Draft section", "SECTION", 3)
        assert neighbours(absent, book) == Neighbours(None, None)  # type: ignore[arg-type]

    def test_a_single_node_book_has_neither_side(self) -> None:
        only = sample_book()[:1]
        assert neighbours(only[0], only) == Neighbours(None, None)  # type: ignore[arg-type]


@pytest.mark.django_db
class TestAgainstTheDatabase:
    def _book(self) -> tuple[object, list[object]]:
        book = BookFactory()
        unit = ContentNodeFactory(book=book, position=1, title="Unit One")
        chapter = ContentNodeFactory(book=book, parent=unit, position=1, title="Chapter One")
        section = ContentNodeFactory(book=book, parent=chapter, position=1, title="Section One")
        later = ContentNodeFactory(book=book, parent=unit, position=2, title="Chapter Two")
        return book, [unit, chapter, section, later]

    def test_the_whole_tree_arrives_in_reading_order(self) -> None:
        book, expected = self._book()
        assert reading_order(book) == expected

    def test_the_table_of_contents_nests_from_one_query(self) -> None:
        book, _ = self._book()
        toc = table_of_contents(book)
        assert [entry.title for entry in toc] == ["Unit One"]
        assert [entry.title for entry in toc[0].children] == ["Chapter One", "Chapter Two"]

    def test_ancestors_are_outermost_first(self) -> None:
        _, (unit, chapter, section, _) = self._book()
        assert ancestors_of(section) == [unit, chapter]

    def test_a_top_level_node_has_no_ancestors_and_costs_no_query(
        self, django_assert_num_queries: object
    ) -> None:
        _, (unit, *_rest) = self._book()
        with django_assert_num_queries(0):  # type: ignore[operator]
            assert ancestors_of(unit) == []

    def test_a_books_tree_is_read_in_a_single_query(
        self, django_assert_num_queries: object
    ) -> None:
        book, _ = self._book()
        with django_assert_num_queries(1):  # type: ignore[operator]
            table_of_contents(book)

    def test_one_books_tree_never_includes_another_s(self) -> None:
        book, _ = self._book()
        other = BookFactory()
        ContentNodeFactory(book=other, position=1, title="Elsewhere")
        assert "Elsewhere" not in [node.title for node in reading_order(book)]
