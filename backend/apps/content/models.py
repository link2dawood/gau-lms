"""Books — the root of the content tree.

A book is the whole textbook: the thing a course opens, the thing a search
index is scoped to, and the thing a hierarchy of units, chapters and sections
hangs from (task 2.2).

Content lives here and nowhere near the learning records that point at it
(architecture rule C.4). A reading position refers to a node by its uuid; it
does not belong to the content module, and nothing here knows it exists.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models


class BookStatus(models.TextChoices):
    """Whether a book is offered, and to whom.

    This is the outer of two gates. A book must be PUBLISHED for a student to
    reach any of it; within a published book, each node still shows only its
    published version (task 2.4). Both must say yes, which is what lets an
    editor work on chapter nine of a live textbook without anyone seeing it.
    """

    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class Book(models.Model):
    # Stable internal identifier (rule C.2). Course mappings, content nodes,
    # search documents and reading positions all refer to this.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=512)

    # A readable handle for URLs and for the import tooling to address a book
    # by. Convenience, never identity: renaming a slug must not be able to
    # move a reading position, which is why nothing stores one as a reference.
    slug = models.SlugField(max_length=255, unique=True)

    description = models.TextField(blank=True)

    status = models.CharField(max_length=16, choices=BookStatus.choices, default=BookStatus.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("title",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(title__gt=""),
                name="book_title_not_empty",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_readable(self) -> bool:
        """Whether a student may open this book at all.

        Archived is deliberately not readable and deliberately not deleted:
        a book withdrawn from a course keeps its versions and the reading
        positions that point into it, so re-publishing restores everything
        rather than resurrecting nothing.
        """
        return self.status == BookStatus.PUBLISHED


class NodeType(models.TextChoices):
    """The four levels the textbook is organised into.

    Which types may nest inside which is a rule of the hierarchy service (task
    3.3), not of the database: a check constraint cannot express "a section
    belongs under a chapter" without encoding the whole ladder, and an import
    that produces a slightly irregular tree should be fixable rather than
    rejected at the row.
    """

    UNIT = "UNIT", "Unit"
    CHAPTER = "CHAPTER", "Chapter"
    SECTION = "SECTION", "Section"
    SUBSECTION = "SUBSECTION", "Subsection"


# Width of one position in the materialised path. Four digits allows 9,999
# siblings at a level, which is far beyond any textbook, and keeps the path
# sortable as plain text — "0002" sorts before "0010", where "2" would not.
PATH_SEGMENT_WIDTH = 4
PATH_SEPARATOR = "."


class ContentNode(models.Model):
    """One unit, chapter, section or subsection.

    The tree is stored twice over: as a `parent` relation, which is the truth,
    and as a `path`, which is the truth flattened into something a database can
    sort and range-scan. The second exists because the reader needs the whole
    table of contents on every page load, and walking a parent relation costs
    one query per level.

    With a path, the operations task 2.3 needs are each a single query:

    * the full tree, in reading order — `ORDER BY path`
    * a subtree — `path LIKE '0001.0003.%'`
    * the ancestors of a node — its path's own prefixes, matched with `IN`
    * the next and previous node, across sibling and parent boundaries alike —
      the rows either side of it in path order, which is why crossing from the
      last section of one chapter into the next chapter needs no special case

    The path is **derived**, never authored. `position` is what an editor
    changes; the hierarchy service (task 3.3) recomputes paths for the moved
    subtree in the same transaction. A path edited by hand is a tree that
    disagrees with itself.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT throughout: neither a book nor a node is deleted by this
    # platform, and an attempt should fail loudly rather than quietly take a
    # subtree — and every reading position in it — with it.
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="nodes")
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="children", null=True, blank=True
    )

    node_type = models.CharField(max_length=16, choices=NodeType.choices)
    title = models.CharField(max_length=512)

    # Order among siblings. The hierarchy service keeps these distinct; the
    # ordering below carries a tiebreak anyway, so a transient duplicate during
    # a reorder cannot make the tree order unstable.
    position = models.PositiveIntegerField(default=0)

    # The materialised path, e.g. "0001.0003.0002". Indexed, because every read
    # of the tree sorts or range-scans on it.
    path = models.CharField(max_length=64, db_index=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("path", "id")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(title__gt=""),
                name="content_node_title_not_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(path__gt=""),
                name="content_node_path_not_empty",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            # Every tree read is scoped to one book and ordered by path.
            models.Index(fields=["book", "path"], name="content_node_tree_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_node_type_display()}: {self.title}"

    @staticmethod
    def segment(position: int) -> str:
        """One position, rendered so that text ordering matches numeric order."""
        return str(position).zfill(PATH_SEGMENT_WIDTH)

    @staticmethod
    def build_path(parent_path: str, position: int) -> str:
        """The path a node has, given its parent's path and its own position."""
        segment = ContentNode.segment(position)
        return f"{parent_path}{PATH_SEPARATOR}{segment}" if parent_path else segment

    @property
    def depth(self) -> int:
        """How deep this node sits. A unit at the top of a book is 1."""
        return len(self.path.split(PATH_SEPARATOR)) if self.path else 0

    @property
    def ancestor_paths(self) -> list[str]:
        """The paths of this node's ancestors, nearest last.

        Every prefix of a path is an ancestor's path, so resolving a breadcrumb
        is one `IN` query rather than one query per level.
        """
        segments = self.path.split(PATH_SEPARATOR) if self.path else []
        return [PATH_SEPARATOR.join(segments[: index + 1]) for index in range(len(segments) - 1)]
