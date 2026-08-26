"""Canonical replay reader for recorded S0 events and lightweight snapshots.

Replay is a reader of recorded evidence, not a second simulation engine. It never
uses wall-clock time, invokes an adapter, or recreates Pulse state.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from .events import validate_event
from .evidence_evaluator import EvaluationResult, evaluate_evidence
from .model import Event, EventType, Snapshot


REPLAY_ARTIFACT_SCHEMA_VERSION = "1.0"
TIMELINE_ARTIFACT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class RecordedSession:
    """Portable canonical recording: append-ordered events plus snapshots."""

    events: tuple[Event, ...]
    snapshots: tuple[Snapshot, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": REPLAY_ARTIFACT_SCHEMA_VERSION,
            "scenario_id": _single_scenario_id(self.events, self.snapshots),
            "events": [event.as_dict() for event in self.events],
            "snapshots": [snapshot.as_dict() for snapshot in self.snapshots],
        }


@dataclass(frozen=True)
class TimelineEntry:
    """One append-ordered event anchored solely to simulation time."""

    sequence: int
    branch_id: int
    simulation_time_s: float
    event: Event
    snapshot: Snapshot | None
    branch_boundary: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "branch_id": self.branch_id,
            "simulation_time_s": self.simulation_time_s,
            "event": self.event.as_dict(),
            "snapshot": None if self.snapshot is None else self.snapshot.as_dict(),
            "branch_boundary": self.branch_boundary,
        }


@dataclass(frozen=True)
class CanonicalTimeline:
    """Replay-ready timeline with explicit branch boundaries, never narration."""

    scenario_id: str
    entries: tuple[TimelineEntry, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": TIMELINE_ARTIFACT_SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "time_axis": "simulation_time_s",
            "entries": [entry.as_dict() for entry in self.entries],
        }


def record_session(events: Sequence[Event], snapshots: Sequence[Snapshot]) -> RecordedSession:
    """Validate and freeze a canonical evidence read model in append order."""

    materialized_events = tuple(events)
    materialized_snapshots = tuple(snapshots)
    _single_scenario_id(materialized_events, materialized_snapshots)
    for event in materialized_events:
        validate_event(event)
    for snapshot in materialized_snapshots:
        if snapshot.simulation_time_s < 0:
            raise ValueError("Snapshot simulation time cannot be negative")
    return RecordedSession(events=materialized_events, snapshots=materialized_snapshots)


def recorded_session_from_dict(raw: Mapping[str, Any]) -> RecordedSession:
    """Load a recorded canonical session without executing any physiology."""

    if set(raw) != {"schema_version", "scenario_id", "events", "snapshots"}:
        raise ValueError("Recorded session has unsupported fields")
    if raw.get("schema_version") != REPLAY_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("Unsupported recorded-session schema version")
    if not isinstance(raw.get("scenario_id"), str) or not raw["scenario_id"]:
        raise ValueError("Recorded session requires a scenario_id")
    events_raw = raw.get("events")
    snapshots_raw = raw.get("snapshots")
    if not isinstance(events_raw, list) or not isinstance(snapshots_raw, list):
        raise ValueError("Recorded session events and snapshots must be arrays")
    events = tuple(_event_from_dict(item) for item in events_raw)
    snapshots = tuple(_snapshot_from_dict(item) for item in snapshots_raw)
    recorded = record_session(events, snapshots)
    if _single_scenario_id(recorded.events, recorded.snapshots) != raw["scenario_id"]:
        raise ValueError("Recorded session scenario_id does not match contained evidence")
    return recorded


def canonical_timeline(recording: RecordedSession) -> CanonicalTimeline:
    """Build a branch-aware, simulation-time timeline from canonical evidence."""

    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in recording.snapshots}
    branch_id = 0
    entries: list[TimelineEntry] = []
    for sequence, event in enumerate(recording.events, start=1):
        snapshot = None
        if event.event_type == EventType.SNAPSHOT_PUBLISHED:
            snapshot_id = event.payload.get("snapshot_id")
            if not isinstance(snapshot_id, str) or snapshot_id not in snapshots_by_id:
                raise ValueError("snapshot.published event must reference a recorded snapshot")
            snapshot = snapshots_by_id[snapshot_id]
            if snapshot.simulation_time_s != event.simulation_time_s:
                raise ValueError("snapshot.published simulation time must match referenced snapshot")
        boundary = event.event_type == EventType.CHECKPOINT_RESTORED
        entries.append(
            TimelineEntry(
                sequence=sequence,
                branch_id=branch_id,
                simulation_time_s=event.simulation_time_s,
                event=event,
                snapshot=snapshot,
                branch_boundary=boundary,
            )
        )
        if boundary:
            branch_id += 1
    return CanonicalTimeline(scenario_id=_single_scenario_id(recording.events, recording.snapshots), entries=tuple(entries))


def evaluate_recording(recording: RecordedSession) -> EvaluationResult:
    """Run the same pure evaluator over a replayed stream."""

    return evaluate_evidence(recording.events, recording.snapshots)


def serialize_recorded_session(recording: RecordedSession) -> str:
    """Return byte-stable JSON for portable recorded-session artifacts."""

    return json.dumps(recording.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def serialize_timeline(timeline: CanonicalTimeline) -> str:
    """Return byte-stable JSON for debrief-ready structured timeline artifacts."""

    return json.dumps(timeline.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _single_scenario_id(events: Sequence[Event], snapshots: Sequence[Snapshot]) -> str:
    scenario_ids = {event.scenario_id for event in events} | {snapshot.scenario_id for snapshot in snapshots}
    if len(scenario_ids) != 1:
        raise ValueError("Recorded evidence must belong to exactly one scenario")
    return next(iter(scenario_ids))


def _event_from_dict(raw: Any) -> Event:
    if not isinstance(raw, Mapping) or set(raw) != {
        "event_id",
        "scenario_id",
        "simulation_time_s",
        "event_type",
        "actor",
        "payload",
        "source",
        "schema_version",
    }:
        raise ValueError("Recorded event has unsupported fields")
    try:
        event_type = EventType(raw["event_type"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Recorded event type is unsupported") from exc
    if not isinstance(raw["payload"], Mapping):
        raise ValueError("Recorded event payload must be a mapping")
    event = Event(
        event_id=str(raw["event_id"]),
        scenario_id=str(raw["scenario_id"]),
        simulation_time_s=float(raw["simulation_time_s"]),
        event_type=event_type,
        actor=str(raw["actor"]),
        payload=dict(raw["payload"]),
        source=str(raw["source"]),
        schema_version=str(raw["schema_version"]),
    )
    validate_event(event)
    return event


def _snapshot_from_dict(raw: Any) -> Snapshot:
    if not isinstance(raw, Mapping) or set(raw) != {
        "snapshot_id",
        "scenario_id",
        "simulation_time_s",
        "engine_version",
        "telemetry",
        "reason",
    }:
        raise ValueError("Recorded snapshot has unsupported fields")
    if not isinstance(raw["telemetry"], Mapping):
        raise ValueError("Recorded snapshot telemetry must be a mapping")
    telemetry = {str(key): float(value) for key, value in raw["telemetry"].items()}
    snapshot = Snapshot(
        snapshot_id=str(raw["snapshot_id"]),
        scenario_id=str(raw["scenario_id"]),
        simulation_time_s=float(raw["simulation_time_s"]),
        engine_version=str(raw["engine_version"]),
        telemetry=telemetry,
        reason=str(raw["reason"]),
    )
    if snapshot.simulation_time_s < 0:
        raise ValueError("Recorded snapshot simulation time cannot be negative")
    return snapshot
