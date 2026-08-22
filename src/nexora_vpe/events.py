"""In-memory event and snapshot store with narrow envelope validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .model import Event, EventType, Snapshot

_ALLOWED_ACTORS = {"learner", "runtime", "scenario", "system"}
_ALLOWED_SOURCES = {"vpe_core", "physiology_adapter", "scenario_runtime", "future_fast_resolver"}


def validate_event(event: Event) -> None:
    if event.schema_version != "1.0":
        raise ValueError("Unsupported event schema version")
    if not event.event_id or not event.scenario_id:
        raise ValueError("Event requires stable event_id and scenario_id")
    if event.simulation_time_s < 0:
        raise ValueError("Event simulation time cannot be negative")
    if event.actor not in _ALLOWED_ACTORS:
        raise ValueError("Event actor is not permitted")
    if event.source not in _ALLOWED_SOURCES:
        raise ValueError("Event source is not permitted")
    if not isinstance(event.event_type, EventType):
        raise ValueError("Event type must be a known EventType")
    if not isinstance(event.payload, dict):
        raise ValueError("Event payload must be a mapping")


@dataclass
class EvidenceStore:
    """Append-only store for canonical replay: events plus snapshots."""

    _events: list[Event] = field(default_factory=list)
    _snapshots: list[Snapshot] = field(default_factory=list)

    def append_event(self, event: Event) -> None:
        validate_event(event)
        # A checkpoint restore may deliberately return simulation time to an
        # earlier value. Command/event identifiers preserve append order; replay
        # consumers must interpret checkpoint.restore as a branch boundary.
        self._events.append(event)

    def append_snapshot(self, snapshot: Snapshot) -> None:
        if snapshot.simulation_time_s < 0:
            raise ValueError("Snapshot simulation time cannot be negative")
        self._snapshots.append(snapshot)

    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def snapshots(self) -> tuple[Snapshot, ...]:
        return tuple(self._snapshots)

    def timeline(self) -> Iterable[dict[str, object]]:
        for event in self._events:
            yield event.as_dict()
