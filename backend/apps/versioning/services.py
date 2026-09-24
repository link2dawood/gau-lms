"""Public interface of the versioning module.

Other modules reach versions through this file and never import
``apps.versioning.models`` directly (architecture rule C.1). `ContentNode`
arrives from `apps.content.services` for the same reason — the precedent is
D-044, where `Course` was taken from its module's interface rather than its
models.

Everything here answers one question: **which text may a reader see?** That is
the inner gate of D-053, and it is deliberately the only thing this module
offers so far. Allocating version numbers, saving drafts and publishing belong
to task 3.6; reading a node's history side by side belongs to 3.7.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from apps.content.services import ContentNode
from apps.versioning.models import ContentVersion, validate_tiptap_document

__all__ = [
    "ContentVersion",
    "history",
    "published_node_ids",
    "published_version",
    "published_versions_for",
    "validate_tiptap_document",
]


def published_version(node: ContentNode) -> ContentVersion | None:
    """The one version of this node a student may read, if there is one.

    None means the node exists but has never been published — a chapter an
    editor has created and not yet finished. Task 2.6 turns that into a node
    absent from the reading order, not into an empty page.
    """
    return ContentVersion.objects.filter(node=node, is_published=True).first()


def published_versions_for(nodes: Iterable[ContentNode]) -> dict[UUID, ContentVersion]:
    """The published version of each of these nodes, keyed by node id.

    One query for the whole set. The reader holds an entire book's reading
    order on every page load (D-055), so the alternative — asking per node —
    would be a query per chapter of the book.

    Nodes with no published version are simply absent from the mapping, which
    is what makes it usable as a filter as well as a lookup.
    """
    node_ids = [node.pk for node in nodes]
    if not node_ids:
        return {}
    versions = ContentVersion.objects.filter(node_id__in=node_ids, is_published=True)
    return {version.node_id: version for version in versions}


def published_node_ids(nodes: Iterable[ContentNode]) -> set[UUID]:
    """Which of these nodes have something published.

    This is what task 2.6 filters a reading order with before handing it to
    `content.services.neighbours`. Filtering once, in one place, is what stops
    the Next button walking a student into a draft (D-055): a node missing
    from the order has no neighbours rather than the wrong ones.
    """
    return set(published_versions_for(nodes))


def history(node: ContentNode) -> list[ContentVersion]:
    """Every version of this node, newest first.

    The whole of acceptance criterion 10 as a read: nothing is ever removed
    from this list, so what a node said in March is still there in June, with
    the author and the change note that put it there. Task 3.7 renders it.
    """
    return list(ContentVersion.objects.filter(node=node))
