"""Typed contracts for the narrow, formative S0 runtime."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"


class RuntimeState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED_BY_SCENARIO = "PAUSED_BY_SCENARIO"
    PAUSED_BY_SYSTEM = "PAUSED_BY_SYSTEM"
    COMPLETED = "COMPLETED"


class CommandKind(str, Enum):
    ADVANCE_TIME = "advance_time"
    RECORD_HISTORY_INTENT = "record_history_intent"
    RECORD_CLINICAL_HYPOTHESIS = "record_clinical_hypothesis"
    REQUEST_OBSERVATION = "request_observation"
    RECORD_ESCALATION = "record_escalation"
    APPLY_INTERVENTION = "apply_intervention"
    CREATE_CHECKPOINT = "create_checkpoint"
    RESTORE_CHECKPOINT = "restore_checkpoint"


class EventType(str, Enum):
    CLOCK_ADVANCED = "clock.advanced"
    CLINICAL_INTENT_RECORDED = "clinical.intent.recorded"
    CLINICAL_HYPOTHESIS_RECORDED = "clinical.hypothesis.recorded"
    OBSERVATION_REQUESTED = "observation.requested"
    INTERVENTION_APPLIED = "intervention.applied"
    SNAPSHOT_PUBLISHED = "snapshot.published"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    FAST_ACQUISITION_RECORDED = "fast.acquisition.recorded"
    ESCALATION_RECORDED = "escalation.recorded"


@dataclass(frozen=True)
class Command:
    command_id: str
    kind: CommandKind
    actor: str
    payload: Mapping[str, Any]
    submitted_order: int
    request_id: str | None = None


@dataclass(frozen=True)
class Event:
    event_id: str
    scenario_id: str
    simulation_time_s: float
    event_type: EventType
    actor: str
    payload: Mapping[str, Any]
    source: str
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "scenario_id": self.scenario_id,
            "simulation_time_s": self.simulation_time_s,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "payload": dict(self.payload),
            "source": self.source,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class Snapshot:
    """Lightweight canonical-replay state with no restorable engine artifact."""

    snapshot_id: str
    scenario_id: str
    simulation_time_s: float
    engine_version: str
    telemetry: Mapping[str, float]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "scenario_id": self.scenario_id,
            "simulation_time_s": self.simulation_time_s,
            "engine_version": self.engine_version,
            "telemetry": dict(self.telemetry),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CheckpointArtifact:
    """In-session restorable physiology artifact, separate from canonical replay.

    ``engine_state`` is adapter-private metadata. It may contain a local Pulse
    state path and is intentionally not included in a client-facing snapshot.
    """

    checkpoint_id: str
    scenario_id: str
    simulation_time_s: float
    engine_version: str
    engine_state: Mapping[str, Any]
