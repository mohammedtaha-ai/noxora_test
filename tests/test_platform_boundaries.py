"""Tests for scale-ready platform contracts independent from the S0 runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock
import uuid

from nexora_vpe.platform.events import (
    CollectingEventPublisher,
    DataClassification as EventDataClassification,
    PlatformEvent,
    PlatformEventError,
)
from nexora_vpe.platform.ids import IdentifierError, Uuid7Generator, parse_uuid7
from nexora_vpe.platform.object_storage import (
    ArtifactType,
    DataClassification as ArtifactDataClassification,
    LocalFilesystemObjectStorage,
    ObjectStorageError,
    RetentionClass,
)
from nexora_vpe.platform.outbox import SQLiteTransactionalOutbox
from nexora_vpe.platform.tenancy import TenantEntityRef, TenantScope


_BASE_TIME = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


class _FailingPublisher:
    def publish(self, event: PlatformEvent) -> None:
        raise RuntimeError(f"simulated publisher outage for {event.event_id}")


class PlatformIdentifierTests(unittest.TestCase):
    def test_uuid7_is_parseable_and_monotonic_inside_one_generator_millisecond(self) -> None:
        generator = Uuid7Generator()
        with mock.patch("nexora_vpe.platform.ids.time.time_ns", return_value=1_725_000_000_000_000_000):
            identifiers = [generator.new() for _ in range(4)]
        self.assertEqual(identifiers, sorted(identifiers))
        self.assertEqual(4, len(set(identifiers)))
        self.assertTrue(all(parse_uuid7(value).version == 7 for value in identifiers))

    def test_uuid7_rejects_wrong_version_and_tenant_refs_require_explicit_scope(self) -> None:
        with self.assertRaises(IdentifierError):
            parse_uuid7(str(uuid.uuid4()))
        scope = TenantScope("tenant-alpha")
        entity = TenantEntityRef(scope=scope, entity_type="simulation_session", entity_id="session-1")
        self.assertEqual("tenant-alpha", entity.scope.tenant_id)
        with self.assertRaises(IdentifierError):
            TenantScope(" ")


class PlatformEventTests(unittest.TestCase):
    def _event(self, *, event_id: str = "", payload: dict[str, object] | None = None) -> PlatformEvent:
        return PlatformEvent(
            event_id=event_id,
            event_type="simulation.session.started",
            schema_version=1,
            occurred_at=_BASE_TIME,
            producer="simulation.data-plane",
            scope=TenantScope("tenant-alpha"),
            aggregate_type="simulation_session",
            aggregate_id="session-alpha",
            routing_key="session-alpha",
            classification=EventDataClassification.INTERNAL,
            payload={} if payload is None else payload,
        )

    def test_event_is_versioned_json_ready_and_does_not_require_runtime_import(self) -> None:
        event = self._event(payload={"scenario_version_id": "scenario-v1"})
        serialized = event.as_dict()
        self.assertEqual(event.event_id, serialized["event_id"])
        self.assertEqual("tenant-alpha", serialized["tenant_id"])
        self.assertNotIn("scope", serialized)
        self.assertEqual("INTERNAL", serialized["classification"])
        self.assertEqual("2026-08-23T12:00:00Z", serialized["occurred_at"])

    def test_event_matches_required_portable_json_schema_fields(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "platform-event-envelope.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        serialized = self._event(payload={"scenario_version_id": "scenario-v1"}).as_dict()
        self.assertTrue(set(schema["required"]).issubset(serialized))
        self.assertTrue(set(serialized).issubset(schema["properties"]))
        self.assertNotIn("scope", serialized)

    def test_event_rejects_nonportable_names_and_non_json_payload(self) -> None:
        with self.assertRaises(PlatformEventError):
            self._event(payload={"not_json": object()})
        with self.assertRaises(PlatformEventError):
            PlatformEvent(
                event_type="Simulation Session Started",
                schema_version=1,
                occurred_at=_BASE_TIME,
                producer="simulation.data-plane",
                scope=TenantScope("tenant-alpha"),
                aggregate_type="simulation_session",
                aggregate_id="session-alpha",
                routing_key="session-alpha",
                classification=EventDataClassification.INTERNAL,
                payload={},
            )


class TransactionalOutboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.outbox = SQLiteTransactionalOutbox(f"{self.temporary_directory.name}/outbox.sqlite3")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _event() -> PlatformEvent:
        return PlatformEvent(
            event_type="simulation.session.completed",
            schema_version=1,
            occurred_at=_BASE_TIME,
            producer="simulation.data-plane",
            scope=TenantScope("tenant-alpha"),
            aggregate_type="simulation_session",
            aggregate_id="session-alpha",
            routing_key="session-alpha",
            classification=EventDataClassification.INTERNAL,
            payload={"completion_status": "COMPLETED"},
        )

    def test_domain_commit_and_outbox_insert_are_atomic_on_duplicate_event_failure(self) -> None:
        event = self._event()
        self.outbox.commit_domain_event(
            domain_key="session-alpha",
            domain_value={"status": "COMPLETED"},
            event=event,
            now=_BASE_TIME,
        )
        self.assertEqual({"status": "COMPLETED"}, self.outbox.domain_value("session-alpha"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.outbox.commit_domain_event(
                domain_key="session-alpha",
                domain_value={"status": "TAMPERED"},
                event=event,
                now=_BASE_TIME + timedelta(seconds=1),
            )
        self.assertEqual({"status": "COMPLETED"}, self.outbox.domain_value("session-alpha"))
        self.assertEqual([event.event_id], [record.event.event_id for record in self.outbox.pending_records()])

    def test_publisher_failure_leaves_record_pending_and_retry_marks_it_published(self) -> None:
        event = self._event()
        self.outbox.commit_domain_event(
            domain_key="session-alpha",
            domain_value={"status": "COMPLETED"},
            event=event,
            now=_BASE_TIME,
        )
        with self.assertRaisesRegex(RuntimeError, "simulated publisher outage"):
            self.outbox.publish_claims(publisher=_FailingPublisher(), worker_id="relay-a")
        pending = self.outbox.pending_records()
        self.assertEqual(1, len(pending))
        self.assertEqual(1, pending[0].attempt_count)

        publisher = CollectingEventPublisher()
        self.assertEqual(1, self.outbox.publish_claims(publisher=publisher, worker_id="relay-b"))
        record = self.outbox.record(event.event_id)
        assert record is not None
        self.assertIsNotNone(record.published_at)
        self.assertEqual(2, record.attempt_count)
        self.assertEqual([event.event_id], [published.event_id for published in publisher.published])

    def test_crash_after_publish_before_mark_allows_duplicate_delivery_for_idempotent_consumers(self) -> None:
        event = self._event()
        self.outbox.commit_domain_event(
            domain_key="session-alpha",
            domain_value={"status": "COMPLETED"},
            event=event,
            now=_BASE_TIME,
        )
        first_claim = self.outbox.claim_pending(
            worker_id="relay-a", limit=1, lease_seconds=1.0, now=_BASE_TIME
        )[0]
        publisher = CollectingEventPublisher()
        publisher.publish(first_claim.record.event)

        retry_claim = self.outbox.claim_pending(
            worker_id="relay-b", limit=1, lease_seconds=10.0, now=_BASE_TIME + timedelta(seconds=2)
        )[0]
        publisher.publish(retry_claim.record.event)
        self.outbox.mark_published(retry_claim, now=_BASE_TIME + timedelta(seconds=2))

        self.assertEqual(2, len(publisher.published))
        self.assertEqual({event.event_id}, {published.event_id for published in publisher.published})
        record = self.outbox.record(event.event_id)
        assert record is not None
        self.assertEqual(2, record.attempt_count)
        self.assertIsNotNone(record.published_at)


class LocalObjectStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.storage = LocalFilesystemObjectStorage(self.temporary_directory.name)
        self.scope = TenantScope("tenant-alpha")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _put(self, *, metadata: dict[str, object] | None = None):
        return self.storage.put(
            content=b"scenario asset bytes",
            content_type="application/octet-stream",
            artifact_type=ArtifactType.SCENARIO_ASSET,
            classification=ArtifactDataClassification.INTERNAL,
            retention_class=RetentionClass.PRODUCT_ASSET,
            scope=self.scope,
            metadata={"scenario_version_id": "scenario-v1"} if metadata is None else metadata,
        )

    def test_local_storage_is_content_addressed_immutable_and_verifiable(self) -> None:
        record = self._put()
        duplicate = self._put()
        self.assertEqual(record, duplicate)
        self.assertEqual(b"scenario asset bytes", self.storage.get(record))
        self.assertTrue(self.storage.verify(record))
        with self.assertRaises(ObjectStorageError):
            self._put(metadata={"scenario_version_id": "scenario-v2"})

    def test_tampered_bytes_fail_verification_and_read(self) -> None:
        record = self._put()
        path = self.storage._root / record.storage_key
        path.write_bytes(b"tampered")
        self.assertFalse(self.storage.verify(record))
        with self.assertRaisesRegex(ObjectStorageError, "integrity"):
            self.storage.get(record)


if __name__ == "__main__":
    unittest.main()
