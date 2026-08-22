"""A SQLite-only transactional outbox spike for platform contracts.

It demonstrates the important semantics: a domain write and an immutable event
row commit together; publication happens after commit; relays can retry; and
consumers must remain idempotent.  It is *not* a PostgreSQL production adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from .events import DataClassification, EventPublisher, PlatformEvent
from .ids import new_uuid7, require_identifier
from .tenancy import TenantScope


class OutboxError(RuntimeError):
    """Raised for invalid outbox usage or lost claims."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OutboxError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OutboxError("stored timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def _event_from_mapping(value: Mapping[str, Any]) -> PlatformEvent:
    tenant_id = value.get("tenant_id")
    if not isinstance(tenant_id, str):
        raise OutboxError("stored event tenant_id is invalid")
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise OutboxError("stored event payload is invalid")
    occurred_at = value.get("occurred_at")
    if not isinstance(occurred_at, str):
        raise OutboxError("stored event timestamp is invalid")
    return PlatformEvent(
        event_id=str(value.get("event_id", "")),
        event_type=str(value.get("event_type", "")),
        schema_version=value.get("schema_version"),
        occurred_at=_parse_time(occurred_at),
        producer=str(value.get("producer", "")),
        scope=TenantScope(tenant_id=tenant_id),
        aggregate_type=str(value.get("aggregate_type", "")),
        aggregate_id=str(value.get("aggregate_id", "")),
        routing_key=str(value.get("routing_key", "")),
        classification=DataClassification(str(value.get("classification", ""))),
        payload=dict(payload),
        correlation_id=value.get("correlation_id"),
        causation_id=value.get("causation_id"),
        trace_id=value.get("trace_id"),
    )


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    """Persisted, immutable event record with delivery bookkeeping."""

    event: PlatformEvent
    created_at: datetime
    attempt_count: int
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class OutboxClaim:
    """A short-lived relay claim protected by a fencing token."""

    record: OutboxRecord
    claim_token: str
    claimed_by: str
    claim_expires_at: datetime


class SQLiteTransactionalOutbox:
    """SQLite local spike for atomic domain mutation plus outbox insertion.

    A caller supplies a simple JSON-serializable domain value only to prove
    transaction behavior.  Production business repositories would own domain
    schema and execute the corresponding PostgreSQL transaction.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS domain_state (
                    domain_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_outbox (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    routing_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    claim_token TEXT,
                    claimed_by TEXT,
                    claim_expires_at TEXT,
                    published_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS platform_outbox_pending_idx
                ON platform_outbox (published_at, claim_expires_at, created_at)
                """
            )

    def commit_domain_event(
        self,
        *,
        domain_key: str,
        domain_value: Mapping[str, Any],
        event: PlatformEvent,
        now: datetime | None = None,
    ) -> None:
        """Atomically upsert a local domain value and insert one outbox event.

        A duplicate `event_id` raises and rolls back the accompanying domain
        mutation.  The method deliberately exposes no broker interaction.
        """

        key = require_identifier(domain_key, field_name="domain_key")
        try:
            encoded_value = json.dumps(dict(domain_value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise OutboxError("domain_value must be JSON serializable") from exc
        committed_at = now or _utc_now()
        envelope = json.dumps(event.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO domain_state(domain_key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(domain_key) DO UPDATE SET
                        value_json = excluded.value_json,
                        updated_at = excluded.updated_at
                    """,
                    (key, encoded_value, _serialize_time(committed_at)),
                )
                connection.execute(
                    """
                    INSERT INTO platform_outbox(
                        event_id, tenant_id, aggregate_type, aggregate_id, routing_key,
                        event_type, schema_version, envelope_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.scope.tenant_id,
                        event.aggregate_type,
                        event.aggregate_id,
                        event.routing_key,
                        event.event_type,
                        event.schema_version,
                        envelope,
                        _serialize_time(committed_at),
                    ),
                )
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def domain_value(self, domain_key: str) -> dict[str, Any] | None:
        """Return the local spike's domain value, if it was committed."""

        key = require_identifier(domain_key, field_name="domain_key")
        with self._connection() as connection:
            row = connection.execute("SELECT value_json FROM domain_state WHERE domain_key = ?", (key,)).fetchone()
        return None if row is None else json.loads(str(row["value_json"]))

    def claim_pending(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: float,
        now: datetime | None = None,
    ) -> list[OutboxClaim]:
        """Claim publishable records without publishing under the SQLite lock."""

        worker = require_identifier(worker_id, field_name="worker_id")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise OutboxError("limit must be a positive integer")
        if not isinstance(lease_seconds, (int, float)) or isinstance(lease_seconds, bool) or lease_seconds <= 0:
            raise OutboxError("lease_seconds must be positive")
        current = now or _utc_now()
        expiry = current + timedelta(seconds=float(lease_seconds))
        claims: list[OutboxClaim] = []

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM platform_outbox
                    WHERE published_at IS NULL
                      AND (claim_expires_at IS NULL OR claim_expires_at <= ?)
                    ORDER BY created_at, event_id
                    LIMIT ?
                    """,
                    (_serialize_time(current), limit),
                ).fetchall()
                for row in rows:
                    claim_token = new_uuid7()
                    result = connection.execute(
                        """
                        UPDATE platform_outbox
                        SET claim_token = ?, claimed_by = ?, claim_expires_at = ?,
                            attempt_count = attempt_count + 1
                        WHERE event_id = ? AND published_at IS NULL
                          AND (claim_expires_at IS NULL OR claim_expires_at <= ?)
                        """,
                        (
                            claim_token,
                            worker,
                            _serialize_time(expiry),
                            row["event_id"],
                            _serialize_time(current),
                        ),
                    )
                    if result.rowcount != 1:
                        continue
                    claims.append(
                        OutboxClaim(
                            record=self._row_to_record(row, attempt_count=int(row["attempt_count"]) + 1),
                            claim_token=claim_token,
                            claimed_by=worker,
                            claim_expires_at=expiry,
                        )
                    )
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")
        return claims

    def mark_published(self, claim: OutboxClaim, *, now: datetime | None = None) -> None:
        """Mark a still-owned claim delivered; stale claims are rejected."""

        published_at = now or _utc_now()
        with self._connection() as connection:
            result = connection.execute(
                """
                UPDATE platform_outbox
                SET published_at = ?, claim_token = NULL, claimed_by = NULL, claim_expires_at = NULL
                WHERE event_id = ? AND claim_token = ? AND claimed_by = ? AND published_at IS NULL
                """,
                (
                    _serialize_time(published_at),
                    claim.record.event.event_id,
                    claim.claim_token,
                    claim.claimed_by,
                ),
            )
        if result.rowcount != 1:
            raise OutboxError("outbox claim is stale or already published")

    def release_claim(self, claim: OutboxClaim) -> None:
        """Release a failed publish claim so a later relay attempt can retry."""

        with self._connection() as connection:
            result = connection.execute(
                """
                UPDATE platform_outbox
                SET claim_token = NULL, claimed_by = NULL, claim_expires_at = NULL
                WHERE event_id = ? AND claim_token = ? AND claimed_by = ? AND published_at IS NULL
                """,
                (claim.record.event.event_id, claim.claim_token, claim.claimed_by),
            )
        if result.rowcount != 1:
            raise OutboxError("outbox claim is stale or already published")

    def publish_claims(self, *, publisher: EventPublisher, worker_id: str, limit: int = 10) -> int:
        """Publish claimed events; failure leaves the failed record pending for retry."""

        claims = self.claim_pending(worker_id=worker_id, limit=limit, lease_seconds=30.0)
        delivered = 0
        for claim in claims:
            try:
                publisher.publish(claim.record.event)
            except BaseException:
                self.release_claim(claim)
                raise
            self.mark_published(claim)
            delivered += 1
        return delivered

    def pending_records(self) -> list[OutboxRecord]:
        """List unpublished records in deterministic local-spike order."""

        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM platform_outbox WHERE published_at IS NULL ORDER BY created_at, event_id"
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def record(self, event_id: str) -> OutboxRecord | None:
        """Return delivery state for one event ID."""

        with self._connection() as connection:
            row = connection.execute("SELECT * FROM platform_outbox WHERE event_id = ?", (event_id,)).fetchone()
        return None if row is None else self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: sqlite3.Row, *, attempt_count: int | None = None) -> OutboxRecord:
        try:
            envelope = json.loads(str(row["envelope_json"]))
        except (TypeError, ValueError) as exc:
            raise OutboxError("stored event envelope is not valid JSON") from exc
        if not isinstance(envelope, Mapping):
            raise OutboxError("stored event envelope must be an object")
        published_value = row["published_at"]
        return OutboxRecord(
            event=_event_from_mapping(envelope),
            created_at=_parse_time(str(row["created_at"])),
            attempt_count=int(row["attempt_count"]) if attempt_count is None else attempt_count,
            published_at=None if published_value is None else _parse_time(str(published_value)),
        )
