"""Versioned platform event contracts independent from S0 runtime events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import re
from typing import Any, Mapping, Protocol

from .ids import new_uuid7, parse_uuid7, require_identifier
from .tenancy import TenantScope


_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$")
_PRODUCER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z][a-z0-9_]*)+$")


class PlatformEventError(ValueError):
    """Raised when a platform event violates its portable boundary contract."""


class DataClassification(str, Enum):
    """Minimum data handling labels; labels do not grant access by themselves."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"


def utc_now() -> datetime:
    """Return an aware UTC timestamp rounded only by the caller's serializer."""

    return datetime.now(timezone.utc)


def _validate_json_object(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise PlatformEventError("payload must be a mapping")
    copied = dict(payload)
    try:
        json.dumps(copied, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise PlatformEventError("payload must be JSON serializable") from exc
    return copied


def _validate_bounded_optional_identifier(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return require_identifier(value, field_name=field_name)


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    """Immutable platform-level event safe for outbox or future bus delivery.

    The payload is intentionally JSON-compatible and may not carry S0/Pulse
    internal state.  This contract validates structure, not business
    authorization or privacy classification policy beyond the supplied label.
    """

    event_type: str
    schema_version: int
    producer: str
    scope: TenantScope
    aggregate_type: str
    aggregate_id: str
    routing_key: str
    classification: DataClassification
    payload: Mapping[str, Any]
    event_id: str = ""
    occurred_at: datetime | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, str) or not _EVENT_TYPE_PATTERN.fullmatch(self.event_type):
            raise PlatformEventError("event_type must be lowercase dot-separated words")
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool) or self.schema_version < 1:
            raise PlatformEventError("schema_version must be a positive integer")
        if not isinstance(self.producer, str) or not _PRODUCER_PATTERN.fullmatch(self.producer):
            raise PlatformEventError("producer must be a lowercase qualified name")
        if not isinstance(self.aggregate_type, str) or not self.aggregate_type.strip():
            raise PlatformEventError("aggregate_type must be a nonempty string")
        aggregate_type = self.aggregate_type.strip()
        if len(aggregate_type) > 64 or any(character.isspace() for character in aggregate_type):
            raise PlatformEventError("aggregate_type must be a short whitespace-free string")
        object.__setattr__(self, "aggregate_type", aggregate_type)
        object.__setattr__(self, "aggregate_id", require_identifier(self.aggregate_id, field_name="aggregate_id"))
        object.__setattr__(self, "routing_key", require_identifier(self.routing_key, field_name="routing_key"))
        if not isinstance(self.classification, DataClassification):
            raise PlatformEventError("classification must be a DataClassification")
        object.__setattr__(self, "payload", _validate_json_object(self.payload))

        identifier = self.event_id or new_uuid7()
        parse_uuid7(identifier)
        object.__setattr__(self, "event_id", identifier)

        timestamp = self.occurred_at or utc_now()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise PlatformEventError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", timestamp.astimezone(timezone.utc))
        object.__setattr__(
            self,
            "correlation_id",
            _validate_bounded_optional_identifier(self.correlation_id, field_name="correlation_id"),
        )
        object.__setattr__(self, "causation_id", _validate_bounded_optional_identifier(self.causation_id, field_name="causation_id"))
        if self.trace_id is not None:
            object.__setattr__(self, "trace_id", require_identifier(self.trace_id, field_name="trace_id"))

    def as_dict(self) -> dict[str, Any]:
        """Return the language-neutral schema representation of this event.

        ``TenantScope`` is a Python convenience type only.  The portable
        envelope carries ``tenant_id`` at top level so that the JSON Schema,
        non-Python generators, and outbox payloads share one public shape.
        """

        values = asdict(self)
        values.pop("scope", None)
        values["tenant_id"] = self.scope.tenant_id
        values["classification"] = self.classification.value
        values["occurred_at"] = self.occurred_at.isoformat().replace("+00:00", "Z")
        return values


class EventPublisher(Protocol):
    """Transport-neutral publisher contract for an already committed event."""

    def publish(self, event: PlatformEvent) -> None:
        """Deliver one event or raise without claiming exactly-once delivery."""


@dataclass(slots=True)
class CollectingEventPublisher:
    """In-memory publisher for tests and local spikes; not a durable relay."""

    published: list[PlatformEvent]

    def __init__(self) -> None:
        self.published = []

    def publish(self, event: PlatformEvent) -> None:
        self.published.append(event)
