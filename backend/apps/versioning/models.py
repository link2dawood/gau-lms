"""Content versions — the history of what a node has said.

This module is the inner of the two gates from D-053. A student sees a node's
text when the *book* is published and *that node's version* is published; both
must say yes, which is what lets an editor rewrite chapter nine of a live
textbook without a reader noticing.

It is also where architecture rule C.3 — non-destructive versioning — becomes a
fact about rows rather than a promise about behaviour. Editing never overwrites
published text. Publishing adds a row; the previous one stays exactly as it was,
still pointing at its author, its timestamp and its change note. "Restore" in
task 3.7 is therefore another forward step, never a rewind.

Nothing here imports `apps.content.models`. The foreign key names its target
lazily, as a string, so the content module's public interface (rule C.1) stays
the only way in.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validate_tiptap_document(value: Any) -> None:
    """Refuse a body that is not a Tiptap document (rule C.7).

    Content is structured, never a blob of HTML: the reader renders from this
    JSON (task 2.7), the search index is built from it one block at a time
    (task 2.11), and both rely on the shape being a document with a list of
    top-level nodes.

    Like every Django validator this runs on ``full_clean()`` and **not** on
    ``save()`` — the same trap D-025 hit with platform registrations. Task 3.6
    must call ``full_clean()`` before writing, or a malformed body is stored
    happily and fails later, in the reader, in front of a student.
    """
    if not isinstance(value, dict):
        raise ValidationError("A version body must be a Tiptap document object.")
    if value.get("type") != "doc":
        raise ValidationError("A version body must have a top-level type of 'doc'.")
    if not isinstance(value.get("content"), list):
        raise ValidationError("A version body must carry a list of content nodes.")


class ContentVersion(models.Model):
    """One saved state of one node's body.

    Versions of a node form a chain: each points back at the one it succeeded,
    and exactly one of them — at most — is the published version a student
    reads. An abandoned draft is still a link in the chain, so the history
    shows the work as well as the result.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Named as a string rather than imported, so this module never reaches into
    # another module's models (rule C.1). PROTECT for the reason it is PROTECT
    # everywhere in this codebase: nothing is deleted, and an attempt should
    # fail loudly instead of quietly taking a node's whole history with it.
    node = models.ForeignKey(
        "content.ContentNode", on_delete=models.PROTECT, related_name="versions"
    )

    # Per node, starting at 1, never reused. **Allocated by task 3.6**, not
    # here: a model that quietly picked the next number would turn two
    # simultaneous publishes into two rows that both believe they are version
    # 3. The unique constraint below makes that race fail loudly instead, which
    # is the only outcome a caller can do anything about.
    version_number = models.PositiveIntegerField()

    # The Tiptap document (rule C.7). JSONB, so a later task can query inside
    # it; validated for shape rather than for schema, because the set of node
    # types grows with the editor (task 3.5) and a version stored years ago
    # must still load.
    body = models.JSONField(validators=[validate_tiptap_document])

    # Who saved it. Null only for versions no person authored — the import
    # pipeline (tasks 3.11 to 3.13) running unattended, or a data migration.
    # PROTECT, so a version never loses its author to an unrelated delete.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="content_versions",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Why this version exists, in the author's words. Blank is allowed here
    # because an autosaved draft has nothing to say yet; task 3.6 decides
    # whether *publishing* may go without one.
    change_note = models.CharField(max_length=500, blank=True)

    # The one version of this node a student may read. At most one per node,
    # enforced below.
    is_published = models.BooleanField(default=False)

    # The version this one succeeded. Null for a node's first version, and
    # unique otherwise, so the history is a chain rather than a tree — see
    # DECISIONS.md D-056.
    previous_version = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="succeeded_by", null=True, blank=True
    )

    class Meta:
        # A total order: (node, version_number) is unique, so this can never
        # be ambiguous. The review of 1.6 found a non-total ordering producing
        # nondeterministic pagination over rows written in one transaction,
        # which is exactly how a publish writes them.
        ordering = ("node", "-version_number")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(version_number__gte=1),
                name="content_version_number_positive",
            ),
            models.UniqueConstraint(
                fields=["node", "version_number"],
                name="unique_version_number_per_node",
            ),
            # The inner gate of D-053, made unambiguous. Without this, two
            # published versions of one node would make "the published body" a
            # question with two answers and no way to choose.
            models.UniqueConstraint(
                fields=["node"],
                condition=models.Q(is_published=True),
                name="one_published_version_per_node",
            ),
            # A version succeeds at most one other, and is succeeded by at most
            # one. PostgreSQL treats NULLs as distinct, so every node's first
            # version passes freely.
            models.UniqueConstraint(
                fields=["previous_version"],
                name="unique_previous_version_link",
            ),
        ]
        # Deliberately no extra indexes. The two unique constraints above are
        # the two reads there are: the published version of a node or of many
        # nodes is served by the partial index on `node` where `is_published`,
        # and a node's history in order is served by (node, version_number).

    def __str__(self) -> str:
        state = "published" if self.is_published else "draft"
        return f"v{self.version_number} of {self.node_id} ({state})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Refuse to re-save a version that is already published.

        A published version is frozen. The only thing that may happen to it is
        withdrawal — `is_published` going false — which changes the flag and
        never the text. Everything else that might want to write to it (fixing
        a typo, amending a change note, re-running an import) is the
        destructive replacement acceptance criterion 10 forbids: the answer is
        always the next version, never this one.

        This is the guard, not the guarantee. `QuerySet.update()` and raw SQL
        go around it, and the publish service in task 3.6 owns the real rule.
        What it catches is the realistic mistake — a code path that edits the
        row a student is reading instead of adding the one after it.

        Deliberately **not** done by remembering the loaded body: that costs a
        deep copy of a whole chapter every time the reader loads a page, and a
        caller mutating `body` in place would still slip past it, because the
        remembered copy would be the same object. A boolean costs nothing and
        has neither weakness.
        """
        if getattr(self, "_was_published", False) and self.is_published:
            raise ValueError(
                "A published version is immutable. Create the next version instead of "
                "rewriting this one (architecture rule C.3)."
            )
        super().save(*args, **kwargs)
        self._was_published = self.is_published

    @classmethod
    def from_db(cls, db: Any, field_names: Any, values: Any) -> ContentVersion:
        """Remember whether this row arrived published, for the guard in `save`.

        No extra query and no extra column read. When `is_published` was
        deferred by `.only()` there is nothing to remember, and the guard
        stands down rather than guessing.
        """
        instance = super().from_db(db, field_names, values)
        instance._was_published = instance.is_published if "is_published" in field_names else False
        return instance
