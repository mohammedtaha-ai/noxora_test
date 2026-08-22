"""Client-safe DTOs for the future learner boundary.

These dataclasses are deliberately distinct from Runtime, Snapshot, Event, and
S0Scenario.  They define the narrow data shape a future learner client may use.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


CLIENT_SCHEMA_VERSION = "1.0"


class ClientCommandStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"


class ClientErrorCode(str, Enum):
    INVALID_COMMAND = "INVALID_COMMAND"
    NOT_ALLOWED = "NOT_ALLOWED"
    INVALID_STATE = "INVALID_STATE"
    DUPLICATE_REQUEST_CONFLICT = "DUPLICATE_REQUEST_CONFLICT"
    AMBIGUOUS_OUTCOME = "AMBIGUOUS_OUTCOME"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    ENGINE_TIMEOUT = "ENGINE_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ClientError:
    code: ClientErrorCode
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True)
class ClientScenarioManifest:
    scenario_id: str
    title: str
    mode: str
    allowed_history_intents: tuple[str, ...]
    allowed_clinical_hypotheses: tuple[str, ...]
    allowed_observation_actions: tuple[str, ...]
    allowed_interventions: tuple[str, ...]
    allowed_escalations: tuple[str, ...]
    visible_telemetry: tuple[str, ...]
    schema_version: str = CLIENT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "mode": self.mode,
            "allowed_history_intents": list(self.allowed_history_intents),
            "allowed_clinical_hypotheses": list(self.allowed_clinical_hypotheses),
            "allowed_observation_actions": list(self.allowed_observation_actions),
            "allowed_interventions": list(self.allowed_interventions),
            "allowed_escalations": list(self.allowed_escalations),
            "visible_telemetry": list(self.visible_telemetry),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ClientRuntimeState:
    runtime_state: str
    simulation_time_s: float
    schema_version: str = CLIENT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_state": self.runtime_state,
            "simulation_time_s": self.simulation_time_s,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ClientSnapshot:
    snapshot_id: str
    scenario_id: str
    simulation_time_s: float
    runtime_state: str
    telemetry: Mapping[str, float]
    schema_version: str = CLIENT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "scenario_id": self.scenario_id,
            "simulation_time_s": self.simulation_time_s,
            "runtime_state": self.runtime_state,
            "telemetry": dict(self.telemetry),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ClientEvent:
    event_id: str
    scenario_id: str
    simulation_time_s: float
    event_type: str
    payload: Mapping[str, str | float]
    schema_version: str = CLIENT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "scenario_id": self.scenario_id,
            "simulation_time_s": self.simulation_time_s,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class CommandRequest:
    kind: str
    payload: Mapping[str, Any]
    request_id: str


@dataclass(frozen=True)
class CommandAccepted:
    request_id: str
    command_id: str
    status: ClientCommandStatus = ClientCommandStatus.ACCEPTED

    def as_dict(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "command_id": self.command_id,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class CommandOutcome:
    request_id: str
    command_id: str | None
    status: ClientCommandStatus
    events: tuple[ClientEvent, ...] = ()
    error: ClientError | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "command_id": self.command_id,
            "status": self.status.value,
            "events": [event.as_dict() for event in self.events],
        }
        if self.error is not None:
            payload["error"] = self.error.as_dict()
        return payload
