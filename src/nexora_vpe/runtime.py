"""Single-owner, headless S0 runtime orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Mapping

from .adapter import PhysiologyAdapter
from .events import EvidenceStore, validate_event_actor
from .model import CheckpointArtifact, Command, CommandKind, Event, EventType, RuntimeState, Snapshot
from .scenario import S0Scenario


@dataclass
class VpeRuntime:
    """Owns simulation time, command order, adapter access, and evidence.

    The runtime accepts only structured commands. Clients, LLMs, and future Unity
    code must submit commands here rather than mutate the physiology adapter.
    """

    scenario: S0Scenario
    adapter: PhysiologyAdapter
    state: RuntimeState = RuntimeState.PAUSED_BY_SCENARIO
    evidence: EvidenceStore = field(default_factory=EvidenceStore)
    _queue: list[Command] = field(default_factory=list)
    _checkpoints: dict[str, CheckpointArtifact] = field(default_factory=dict)
    _event_counter: int = 0
    _snapshot_counter: int = 0
    _submitted_counter: int = 0
    _requests: dict[str, Command] = field(default_factory=dict)
    _request_outcomes: dict[str, tuple[Event, ...]] = field(default_factory=dict)

    def start(self) -> None:
        self.scenario.validate()
        if self.state != RuntimeState.PAUSED_BY_SCENARIO:
            raise RuntimeError("Runtime may only start from PAUSED_BY_SCENARIO")
        self.adapter.bootstrap(self.scenario)
        self.state = RuntimeState.RUNNING
        self._publish_snapshot("scenario_started")

    @property
    def simulation_time_s(self) -> float:
        return self.adapter.simulation_time_s

    def submit(
        self,
        kind: CommandKind,
        actor: str,
        payload: Mapping[str, Any],
        request_id: str | None = None,
    ) -> str:
        """Queue a command or return the existing command for a stable request id.

        The runtime de-duplicates only within its current in-memory session. A
        duplicate with different semantics is rejected rather than re-executed.
        """
        if request_id is not None:
            self._validate_request_id(request_id)
            existing = self._requests.get(request_id)
            if existing is not None:
                if existing.kind != kind or existing.actor != actor or dict(existing.payload) != dict(payload):
                    raise ValueError("request_id is already bound to a different command")
                return existing.command_id
        if self.state != RuntimeState.RUNNING:
            raise RuntimeError("Commands are accepted only while the runtime is RUNNING")
        self._submitted_counter += 1
        command = Command(
            command_id=f"cmd-{self._submitted_counter:06d}",
            kind=kind,
            actor=actor,
            payload=dict(payload),
            submitted_order=self._submitted_counter,
            request_id=request_id,
        )
        self._queue.append(command)
        if request_id is not None:
            self._requests[request_id] = command
        return command.command_id

    def drain(self) -> tuple[Event, ...]:
        """Apply all queued commands in submission order and return new events."""
        if self.state != RuntimeState.RUNNING:
            raise RuntimeError("Cannot process a queue unless the runtime is RUNNING")
        starting_index = len(self.evidence.events())
        pending = sorted(self._queue, key=lambda command: command.submitted_order)
        self._queue = []
        for index, command in enumerate(pending):
            event_index = len(self.evidence.events())
            try:
                self._apply(command)
            except Exception:
                # Retain request_id binding even if the adapter outcome is
                # ambiguous. A duplicate can recover the same command id but
                # can never re-execute a potentially side-effecting command.
                # A corrected rejected command must use a new request id.
                # The rejected command is terminally reported by the raised error.
                # Commands after it remain queued, in original order, for an
                # explicit subsequent drain; they are never silently discarded.
                self._queue = pending[index + 1 :] + self._queue
                raise
            if command.request_id is not None:
                self._request_outcomes[command.request_id] = self.evidence.events()[event_index:]
        return self.evidence.events()[starting_index:]

    def complete(self) -> None:
        if self.state != RuntimeState.RUNNING:
            raise RuntimeError("Only a running scenario may complete")
        if self._queue:
            raise RuntimeError("Queue must be drained before completion")
        self.state = RuntimeState.COMPLETED

    def events(self) -> tuple[Event, ...]:
        return self.evidence.events()

    def snapshots(self) -> tuple[Snapshot, ...]:
        return self.evidence.snapshots()

    def checkpoint_artifacts(self) -> tuple[CheckpointArtifact, ...]:
        """Return in-session restorable artifacts, never canonical snapshots."""
        return tuple(self._checkpoints.values())

    def queued_command_ids(self) -> tuple[str, ...]:
        """Expose retained command order for runtime-contract diagnostics/tests."""
        return tuple(command.command_id for command in sorted(self._queue, key=lambda item: item.submitted_order))

    def request_outcome(self, request_id: str) -> tuple[Event, ...] | None:
        """Return an accepted in-session outcome, or None while it is unresolved."""
        self._validate_request_id(request_id)
        return self._request_outcomes.get(request_id)

    @staticmethod
    def _validate_request_id(request_id: object) -> None:
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", request_id):
            raise ValueError("request_id must be a stable identifier of at most 128 safe characters")

    def _validate_command(self, command: Command) -> None:
        """Reject all structurally knowable errors before adapter mutation."""
        if not isinstance(command.kind, CommandKind):
            raise ValueError("Unsupported command kind")
        if not isinstance(command.payload, Mapping):
            raise ValueError("Command payload must be a mapping")
        validate_event_actor(command.actor)

        if command.kind == CommandKind.ADVANCE_TIME:
            duration_s = command.payload.get("duration_s")
            if (
                isinstance(duration_s, bool)
                or not isinstance(duration_s, (int, float))
                or not math.isfinite(float(duration_s))
                or duration_s <= 0
            ):
                raise ValueError("advance_time requires a positive finite duration_s")
            return

        if command.kind == CommandKind.RECORD_HISTORY_INTENT:
            if command.payload.get("intent_id") not in self.scenario.allowed_history_intents:
                raise ValueError("History intent is not allowed by scenario")
            return

        if command.kind == CommandKind.RECORD_CLINICAL_HYPOTHESIS:
            hypothesis_id = command.payload.get("hypothesis_id")
            if not isinstance(hypothesis_id, str):
                raise ValueError("record_clinical_hypothesis requires hypothesis_id")
            self.scenario.clinical_hypothesis(hypothesis_id)
            return

        if command.kind == CommandKind.REQUEST_OBSERVATION:
            if command.payload.get("observation_id") not in self.scenario.allowed_observation_ids():
                raise ValueError("Observation is not allowed by scenario")
            return

        if command.kind == CommandKind.RECORD_ESCALATION:
            escalation_id = command.payload.get("escalation_id")
            if not isinstance(escalation_id, str):
                raise ValueError("record_escalation requires escalation_id")
            self.scenario.escalation(escalation_id)
            return

        if command.kind == CommandKind.APPLY_INTERVENTION:
            intervention_id = command.payload.get("intervention_id")
            if not isinstance(intervention_id, str):
                raise ValueError("apply_intervention requires intervention_id")
            self.scenario.intervention(intervention_id)
            return

        if command.kind == CommandKind.CREATE_CHECKPOINT:
            checkpoint_id = command.payload.get("checkpoint_id")
            if not isinstance(checkpoint_id, str) or not checkpoint_id:
                raise ValueError("create_checkpoint requires checkpoint_id")
            if checkpoint_id in self._checkpoints:
                raise ValueError("Checkpoint identifier already exists")
            return

        if command.kind == CommandKind.RESTORE_CHECKPOINT:
            checkpoint_id = command.payload.get("checkpoint_id")
            if checkpoint_id not in self._checkpoints:
                raise ValueError("Unknown checkpoint identifier")
            return

        raise ValueError(f"Unsupported command kind: {command.kind}")

    def _apply(self, command: Command) -> None:
        self._validate_command(command)
        if command.kind == CommandKind.ADVANCE_TIME:
            duration_s = command.payload.get("duration_s")
            if not isinstance(duration_s, (int, float)) or duration_s <= 0:
                raise ValueError("advance_time requires a positive duration_s")
            self.adapter.advance(float(duration_s))
            self._emit(
                EventType.CLOCK_ADVANCED,
                actor=command.actor,
                source="vpe_core",
                payload={"command_id": command.command_id, "duration_s": float(duration_s)},
            )
            self._publish_snapshot("time_advanced")
            return

        if command.kind == CommandKind.RECORD_HISTORY_INTENT:
            intent_id = command.payload.get("intent_id")
            if intent_id not in self.scenario.allowed_history_intents:
                raise ValueError("History intent is not allowed by scenario")
            self._emit(
                EventType.CLINICAL_INTENT_RECORDED,
                actor=command.actor,
                source="scenario_runtime",
                payload={"command_id": command.command_id, "intent_id": intent_id},
            )
            return

        if command.kind == CommandKind.RECORD_CLINICAL_HYPOTHESIS:
            hypothesis_id = command.payload.get("hypothesis_id")
            self._emit(
                EventType.CLINICAL_HYPOTHESIS_RECORDED,
                actor=command.actor,
                source="scenario_runtime",
                payload={"command_id": command.command_id, "hypothesis_id": hypothesis_id},
            )
            return

        if command.kind == CommandKind.REQUEST_OBSERVATION:
            observation_id = command.payload.get("observation_id")
            self._emit(
                EventType.OBSERVATION_REQUESTED,
                actor=command.actor,
                source="scenario_runtime",
                payload={"command_id": command.command_id, "observation_id": observation_id},
            )
            return

        if command.kind == CommandKind.RECORD_ESCALATION:
            escalation_id = command.payload.get("escalation_id")
            if not isinstance(escalation_id, str):
                raise ValueError("record_escalation requires escalation_id")
            definition = self.scenario.escalation(escalation_id)
            self._emit(
                EventType.ESCALATION_RECORDED,
                actor=command.actor,
                source="scenario_runtime",
                payload={
                    "command_id": command.command_id,
                    "escalation_id": definition.escalation_id,
                },
            )
            return

        if command.kind == CommandKind.APPLY_INTERVENTION:
            intervention_id = command.payload.get("intervention_id")
            if not isinstance(intervention_id, str):
                raise ValueError("apply_intervention requires intervention_id")
            definition = self.scenario.intervention(intervention_id)
            self.adapter.apply_intervention(definition.as_adapter_payload())
            self._emit(
                EventType.INTERVENTION_APPLIED,
                actor=command.actor,
                source="physiology_adapter",
                payload={
                    "command_id": command.command_id,
                    "intervention_id": definition.intervention_id,
                    "compound": definition.pulse_compound,
                    "volume_ml": definition.volume_ml,
                    "rate_ml_min": definition.rate_ml_min,
                },
            )
            self._publish_snapshot("intervention_applied")
            return

        if command.kind == CommandKind.CREATE_CHECKPOINT:
            checkpoint_id = command.payload.get("checkpoint_id")
            if not isinstance(checkpoint_id, str) or not checkpoint_id:
                raise ValueError("create_checkpoint requires checkpoint_id")
            if checkpoint_id in self._checkpoints:
                raise ValueError("Checkpoint identifier already exists")
            engine_state = dict(self.adapter.save_state())
            self._checkpoints[checkpoint_id] = CheckpointArtifact(
                checkpoint_id=checkpoint_id,
                scenario_id=self.scenario.scenario_id,
                simulation_time_s=self.adapter.simulation_time_s,
                engine_version=self.adapter.engine_version,
                engine_state=engine_state,
            )
            self._emit(
                EventType.CHECKPOINT_CREATED,
                actor=command.actor,
                source="physiology_adapter",
                payload={"command_id": command.command_id, "checkpoint_id": checkpoint_id},
            )
            self._publish_snapshot(f"checkpoint:{checkpoint_id}")
            return

        if command.kind == CommandKind.RESTORE_CHECKPOINT:
            checkpoint_id = command.payload.get("checkpoint_id")
            if checkpoint_id not in self._checkpoints:
                raise ValueError("Unknown checkpoint identifier")
            self.adapter.restore_state(self._checkpoints[checkpoint_id].engine_state)
            self._emit(
                EventType.CHECKPOINT_RESTORED,
                actor=command.actor,
                source="physiology_adapter",
                payload={"command_id": command.command_id, "checkpoint_id": checkpoint_id},
            )
            self._publish_snapshot(f"checkpoint_restored:{checkpoint_id}")
            return

        raise ValueError(f"Unsupported command kind: {command.kind}")

    def _emit(self, event_type: EventType, actor: str, source: str, payload: Mapping[str, Any]) -> None:
        self._event_counter += 1
        self.evidence.append_event(
            Event(
                event_id=f"evt-{self._event_counter:06d}",
                scenario_id=self.scenario.scenario_id,
                simulation_time_s=self.adapter.simulation_time_s,
                event_type=event_type,
                actor=actor,
                payload=dict(payload),
                source=source,
            )
        )

    def _publish_snapshot(self, reason: str) -> None:
        self._snapshot_counter += 1
        snapshot = Snapshot(
            snapshot_id=f"snp-{self._snapshot_counter:06d}",
            scenario_id=self.scenario.scenario_id,
            simulation_time_s=self.adapter.simulation_time_s,
            engine_version=self.adapter.engine_version,
            telemetry=self.adapter.telemetry(self.scenario.telemetry_keys),
            reason=reason,
        )
        self.evidence.append_snapshot(snapshot)
        self._emit(
            EventType.SNAPSHOT_PUBLISHED,
            actor="runtime",
            source="vpe_core",
            payload={"snapshot_id": snapshot.snapshot_id, "reason": reason},
        )
