"""Public interface of the content module.

Other modules reach books and nodes through this file and never import
``apps.content.models`` directly (architecture rule C.1).

Everything here is built on the materialised path (D-054). A book's whole tree
is one indexed query in reading order; the nesting, the breadcrumb and the
previous/next links are then derived from that one result in memory, because a
textbook has hundreds of nodes, not millions, and the reader needs the table of
contents on every page anyway.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.content.models import Book, BookStatus, ContentNode, NodeType

__all__ = [
    "Book",
    "BookStatus",
    "ContentNode",
    "Neighbours",
    "NodeType",
    "TocEntry",
    "ancestors_of",
    "neighbours",
    "nest",
    "reading_order",
    "table_of_contents",
]


@dataclass
class TocEntry:
    """One line of a table of contents, with its own children nested under it."""

    id: str
    title: str
    node_type: str
    depth: int
    children: list[TocEntry] = field(default_factory=list)


@dataclass(frozen=True)
class Neighbours:
    """What comes before and after a node in reading order.

    Either may be absent: the first node of a book has no previous, the last
    has no next. That is the only boundary there is — chapter and unit
    boundaries are not special, because reading order already crosses them.
    """

    previous: ContentNode | None
    next: ContentNode | None


def reading_order(book: Book) -> list[ContentNode]:
    """Every node in the book, in the order a reader meets them.

    One query. The model's ordering is `("path", "id")`, and the path is
    constructed so that text order is reading order — a parent before its
    children, and a chapter's last section before the next chapter.
    """
    return list(ContentNode.objects.filter(book=book))


def table_of_contents(book: Book) -> list[TocEntry]:
    """The book's tree, nested, from a single query."""
    return nest(reading_order(book))


def nest(nodes: list[ContentNode]) -> list[TocEntry]:
    """Turn a path-ordered list into nested entries.

    Nesting is decided by depth rather than by following parent ids, so this
    costs nothing beyond the one query and works on any prefix of the tree —
    which is what lets a published-only reading order (task 2.6) nest without
    a second pass.

    A node whose parent is missing from the list attaches to the nearest
    shallower entry instead of disappearing. Imports produce irregular trees
    (task 3.13), and a chapter silently absent from the contents is a worse
    outcome than one shown a level too high.
    """
    roots: list[TocEntry] = []
    open_entries: list[tuple[int, TocEntry]] = []

    for node in nodes:
        entry = TocEntry(
            id=str(node.pk),
            title=node.title,
            node_type=node.node_type,
            depth=node.depth,
        )
        while open_entries and open_entries[-1][0] >= node.depth:
            open_entries.pop()

        if open_entries:
            open_entries[-1][1].children.append(entry)
        else:
            roots.append(entry)

        open_entries.append((node.depth, entry))

    return roots


def ancestors_of(node: ContentNode) -> list[ContentNode]:
    """The node's ancestors, outermost first — its breadcrumb.

    One query, because every ancestor's path is a prefix of this node's.
    """
    paths = node.ancestor_paths
    if not paths:
        return []
    return list(ContentNode.objects.filter(book_id=node.book_id, path__in=paths))


def neighbours(node: ContentNode, order: list[ContentNode]) -> Neighbours:
    """The nodes either side of this one, within the given reading order.

    Takes the order rather than querying for it: the caller already holds it
    for the table of contents, and passing it means the publication filter is
    applied once, in one place. A node absent from the order — unpublished,
    when the caller filtered — has no neighbours rather than the wrong ones.
    """
    for index, candidate in enumerate(order):
        if candidate.pk == node.pk:
            return Neighbours(
                previous=order[index - 1] if index > 0 else None,
                next=order[index + 1] if index + 1 < len(order) else None,
            )
    return Neighbours(previous=None, next=None)
