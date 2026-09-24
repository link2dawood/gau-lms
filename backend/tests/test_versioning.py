"""Content versions — the inner gate, and the promise that nothing is overwritten.

Two things are being protected here. The first is D-053's inner gate: a student
reads a node when that node has a published version, and a node can never have
two. The second is architecture rule C.3 and acceptance criterion 10 — a
version, once published, is not edited. The next version is how text changes.

Task 3.16 owes the end-to-end half of this: that publishing through the service
creates a version, that a reading position survives it, and that a blockId is
stable across an edit. What is here is the layer those rest on.
"""

from __future__ import annotations

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.versioning.models import ContentVersion, validate_tiptap_document
from apps.versioning.services import (
    history,
    published_node_ids,
    published_version,
    published_versions_for,
)
from tests.factories import ContentNodeFactory, ContentVersionFactory, UserFactory, tiptap_document

pytestmark = pytest.mark.django_db


class TestIdentityAndBody:
    def test_the_identifier_is_a_uuid_not_a_sequence(self) -> None:
        """Rule C.2, as everywhere else. A search document and a reading
        position both point at content by uuid."""
        assert isinstance(ContentVersionFactory().pk, uuid.UUID)

    def test_a_body_round_trips_as_structured_json(self) -> None:
        """Rule C.7. The reader renders from this and the index is built from
        it block by block, so it has to come back as it went in — blockIds
        included."""
        body = tiptap_document("First paragraph.", "Second paragraph.")
        version = ContentVersionFactory(body=body)
        version.refresh_from_db()
        assert version.body == body
        assert [block["attrs"]["blockId"] for block in version.body["content"]] == [
            "block-1",
            "block-2",
        ]

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param("<p>hello</p>", id="a string of html"),
            pytest.param([{"type": "paragraph"}], id="a bare list of blocks"),
            pytest.param({}, id="an empty object"),
            pytest.param({"type": "paragraph", "content": []}, id="not a document"),
            pytest.param({"type": "doc"}, id="no content key"),
            pytest.param({"type": "doc", "content": "text"}, id="content is not a list"),
        ],
    )
    def test_a_body_that_is_not_a_tiptap_document_is_refused(self, body: object) -> None:
        with pytest.raises(ValidationError):
            validate_tiptap_document(body)

    def test_an_empty_document_is_allowed(self) -> None:
        """A section an editor has created and not yet written is a real state.
        It is unpublished, which is what keeps it away from a student."""
        validate_tiptap_document({"type": "doc", "content": []})

    def test_validation_does_not_run_on_save(self) -> None:
        """Recorded because it is a trap, not because it is desirable.

        Django validators run on `full_clean()` and never on `save()` — the
        same trap D-025 hit with platform registrations. **Task 3.6 must call
        `full_clean()`**, or a malformed body is stored without complaint and
        fails much later, in the reader, in front of a student.
        """
        version = ContentVersion(
            node=ContentNodeFactory(), version_number=1, body={"not": "a document"}
        )
        version.save()  # no error, deliberately
        assert ContentVersion.objects.get(pk=version.pk).body == {"not": "a document"}
        with pytest.raises(ValidationError):
            version.full_clean()


class TestTheInnerGate:
    """At most one published version per node (D-053)."""

    def test_a_node_may_have_one_published_version(self) -> None:
        node = ContentNodeFactory()
        version = ContentVersionFactory(node=node, is_published=True)
        assert published_version(node) == version

    def test_a_node_with_nothing_published_reads_as_none(self) -> None:
        """Not an empty page: task 2.6 leaves the node out of the reading order
        entirely, so the Next button cannot land on it."""
        node = ContentNodeFactory()
        ContentVersionFactory(node=node, is_published=False)
        assert published_version(node) is None

    def test_a_node_cannot_have_two_published_versions(self) -> None:
        """Without this, "the published body" is a question with two answers.
        Enforced by a partial unique index, not by application logic."""
        node = ContentNodeFactory()
        ContentVersionFactory(node=node, is_published=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            ContentVersionFactory(node=node, is_published=True)

    def test_a_node_may_have_many_unpublished_versions(self) -> None:
        """Superseded versions and abandoned drafts are both unpublished. The
        constraint is on the published one only."""
        node = ContentNodeFactory()
        ContentVersionFactory.create_batch(3, node=node, is_published=False)
        assert ContentVersion.objects.filter(node=node).count() == 3

    def test_two_nodes_may_each_have_a_published_version(self) -> None:
        first, second = ContentNodeFactory(), ContentNodeFactory()
        ContentVersionFactory(node=first, is_published=True)
        ContentVersionFactory(node=second, is_published=True)
        assert published_version(first) != published_version(second)

    def test_publishing_the_next_version_requires_withdrawing_this_one_first(self) -> None:
        """The order is forced by the constraint and is task 3.6's to get
        right: unpublish, then publish, inside one transaction. Doing it the
        other way round violates the index halfway through, and the constraint
        cannot be deferred."""
        node = ContentNodeFactory()
        first = ContentVersionFactory(node=node, is_published=True)
        with transaction.atomic():
            first.is_published = False
            first.save(update_fields=["is_published"])
            second = ContentVersionFactory(node=node, is_published=True)
        assert published_version(node) == second


class TestVersionNumbers:
    def test_a_number_is_unique_within_a_node(self) -> None:
        """Allocation belongs to task 3.6. This is what makes two simultaneous
        publishes fail loudly instead of both becoming version 3."""
        node = ContentNodeFactory()
        ContentVersionFactory(node=node, version_number=1)
        with pytest.raises(IntegrityError), transaction.atomic():
            ContentVersionFactory(node=node, version_number=1)

    def test_two_nodes_number_their_versions_independently(self) -> None:
        for node in (ContentNodeFactory(), ContentNodeFactory()):
            ContentVersionFactory(node=node, version_number=1)
        assert ContentVersion.objects.filter(version_number=1).count() == 2

    def test_numbering_starts_at_one(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            ContentVersionFactory(version_number=0)


class TestHistoryIsAChain:
    def test_a_version_records_what_it_succeeded(self) -> None:
        node = ContentNodeFactory()
        first = ContentVersionFactory(node=node)
        second = ContentVersionFactory(node=node, previous_version=first)
        assert second.previous_version == first
        assert first.succeeded_by.get() == second

    def test_a_first_version_has_no_predecessor(self) -> None:
        """Null, and PostgreSQL treats nulls as distinct — so every node's
        first version passes the uniqueness below."""
        ContentVersionFactory.create_batch(3, previous_version=None)
        assert ContentVersion.objects.filter(previous_version__isnull=True).count() == 3

    def test_a_version_can_be_succeeded_only_once(self) -> None:
        """History is a chain, not a tree. Two versions claiming the same
        predecessor would make "what came before this" ambiguous, which is the
        opposite of what criterion 10 asks for (D-056)."""
        node = ContentNodeFactory()
        first = ContentVersionFactory(node=node)
        ContentVersionFactory(node=node, previous_version=first)
        with pytest.raises(IntegrityError), transaction.atomic():
            ContentVersionFactory(node=node, previous_version=first)

    def test_history_reads_newest_first(self) -> None:
        node = ContentNodeFactory()
        versions = [ContentVersionFactory(node=node) for _ in range(3)]
        assert [v.version_number for v in versions] == [1, 2, 3]
        assert history(node) == list(reversed(versions))

    def test_history_keeps_what_a_node_used_to_say(self) -> None:
        """Nothing is removed, ever. This is acceptance criterion 10 as a
        read: what the chapter said in March is still there in June, with the
        author and the change note that put it there."""
        node = ContentNodeFactory()
        author = UserFactory()
        ContentVersionFactory(
            node=node,
            body=tiptap_document("The original wording."),
            created_by=author,
            change_note="First draft",
            is_published=True,
        )
        superseded = history(node)[0]
        superseded.is_published = False
        superseded.save(update_fields=["is_published"])
        ContentVersionFactory(node=node, body=tiptap_document("Rewritten."), is_published=True)

        earliest = history(node)[-1]
        assert earliest.body["content"][0]["content"][0]["text"] == "The original wording."
        assert earliest.created_by == author
        assert earliest.change_note == "First draft"


class TestAPublishedVersionIsImmutable:
    def test_a_published_version_cannot_be_re_saved(self) -> None:
        """Rule C.3. The answer to changed text is always the next version."""
        version = ContentVersionFactory(is_published=True)
        version.body = tiptap_document("Quietly rewritten.")
        with pytest.raises(ValueError, match="immutable"):
            version.save()

    def test_the_guard_survives_a_round_trip_through_the_database(self) -> None:
        """The flag is remembered on load, not only on the instance that
        created the row — otherwise the guard would protect nothing that a
        later request touched."""
        version = ContentVersionFactory(is_published=True)
        reloaded = ContentVersion.objects.get(pk=version.pk)
        reloaded.change_note = "Amending the audit trail"
        with pytest.raises(ValueError, match="immutable"):
            reloaded.save()

    def test_a_published_version_may_be_withdrawn(self) -> None:
        """Withdrawal changes the flag and never the text, so it is the one
        thing that may happen to a published version."""
        version = ContentVersionFactory(is_published=True)
        version.is_published = False
        version.save(update_fields=["is_published"])
        version.refresh_from_db()
        assert version.is_published is False
        assert published_version(version.node) is None

    def test_a_draft_may_be_edited_in_place(self) -> None:
        """Task 3.6 updates the working draft on every save. Only publication
        freezes a version."""
        version = ContentVersionFactory(is_published=False)
        version.body = tiptap_document("Still being written.")
        version.save()
        version.refresh_from_db()
        assert version.body["content"][0]["content"][0]["text"] == "Still being written."

    def test_a_draft_may_be_published(self) -> None:
        version = ContentVersionFactory(is_published=False)
        version.is_published = True
        version.save()
        assert published_version(version.node) == version


class TestPublishedLookups:
    def test_it_returns_only_published_versions_keyed_by_node(self) -> None:
        published_node = ContentNodeFactory()
        draft_node = ContentNodeFactory()
        version = ContentVersionFactory(node=published_node, is_published=True)
        ContentVersionFactory(node=draft_node, is_published=False)

        found = published_versions_for([published_node, draft_node])
        assert found == {published_node.pk: version}

    def test_it_costs_one_query_for_a_whole_book(self, django_assert_num_queries: object) -> None:
        """The reader holds an entire book's reading order on every page load
        (D-055). A query per node would be a query per chapter."""
        nodes = ContentNodeFactory.create_batch(5)
        for node in nodes:
            ContentVersionFactory(node=node, is_published=True)
        with django_assert_num_queries(1):  # type: ignore[operator]
            published_versions_for(nodes)

    def test_it_costs_no_query_for_an_empty_set(self, django_assert_num_queries: object) -> None:
        with django_assert_num_queries(0):  # type: ignore[operator]
            assert published_versions_for([]) == {}

    def test_published_node_ids_filters_a_reading_order(self) -> None:
        """The shape task 2.6 needs: take the book's reading order, keep the
        nodes with something published, and hand that to `neighbours`. A node
        left out has no neighbours rather than the wrong ones (D-055), which
        is what stops Next walking a student into a draft."""
        order = ContentNodeFactory.create_batch(3)
        ContentVersionFactory(node=order[0], is_published=True)
        ContentVersionFactory(node=order[2], is_published=True)

        readable = published_node_ids(order)
        assert [node for node in order if node.pk in readable] == [order[0], order[2]]


class TestNothingIsDeleted:
    def test_a_node_with_versions_cannot_be_deleted(self) -> None:
        """PROTECT, as everywhere. A delete that took a node's whole history
        with it should fail loudly rather than succeed quietly."""
        version = ContentVersionFactory()
        with pytest.raises(ProtectedError), transaction.atomic():
            version.node.delete()

    def test_an_author_with_versions_cannot_be_deleted(self) -> None:
        """A version never loses its author to an unrelated delete — that
        attribution is the traceability criterion 10 asks for."""
        author = UserFactory()
        ContentVersionFactory(created_by=author)
        with pytest.raises(ProtectedError), transaction.atomic():
            author.delete()

    def test_a_version_may_have_no_author(self) -> None:
        """Null means no person authored it — the import pipeline running
        unattended (tasks 3.11 to 3.13), or a data migration."""
        assert ContentVersionFactory(created_by=None).created_by is None
