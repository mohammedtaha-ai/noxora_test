"""Single-owner, headless S0 runtime orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .adapter import PhysiologyAdapter
from .events import EvidenceStore
from .model import Command, CommandKind, Event, EventType, RuntimeState, Snapshot
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
    _checkpoint_states: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    _event_counter: int = 0
    _snapshot_counter: int = 0
    _submitted_counter: int = 0

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

    def submit(self, kind: CommandKind, actor: str, payload: Mapping[str, Any]) -> str:
        if self.state != RuntimeState.RUNNING:
            raise RuntimeError("Commands are accepted only while the runtime is RUNNING")
        self._submitted_counter += 1
        command = Command(
            command_id=f"cmd-{self._submitted_counter:06d}",
            kind=kind,
            actor=actor,
            payload=dict(payload),
            submitted_order=self._submitted_counter,
        )
        self._queue.append(command)
        return command.command_id

    def drain(self) -> tuple[Event, ...]:
        """Apply all queued commands in submission order and return new events."""
        if self.state != RuntimeState.RUNNING:
            raise RuntimeError("Cannot process a queue unless the runtime is RUNNING")
        starting_index = len(self.evidence.events())
        pending = sorted(self._queue, key=lambda command: command.submitted_order)
        self._queue = []
        for command in pending:
            self._apply(command)
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

    def _apply(self, command: Command) -> None:
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

        if command.kind == CommandKind.REQUEST_OBSERVATION:
            observation_id = command.payload.get("observation_id")
            if observation_id not in {"FAST", "VITALS", "CBC"}:
                raise ValueError("Observation is not allowed by S0")
            self._emit(
                EventType.OBSERVATION_REQUESTED,
                actor=command.actor,
                source="scenario_runtime",
                payload={"command_id": command.command_id, "observation_id": observation_id},
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
            if checkpoint_id in self._checkpoint_states:
                raise ValueError("Checkpoint identifier already exists")
            self._checkpoint_states[checkpoint_id] = dict(self.adapter.save_state())
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
            if checkpoint_id not in self._checkpoint_states:
                raise ValueError("Unknown checkpoint identifier")
            self.adapter.restore_state(self._checkpoint_states[checkpoint_id])
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
            adapter_state=self.adapter.save_state(),
            reason=reason,
        )
        self.evidence.append_snapshot(snapshot)
        self._emit(
            EventType.SNAPSHOT_PUBLISHED,
            actor="runtime",
            source="vpe_core",
            payload={"snapshot_id": snapshot.snapshot_id, "reason": reason},
        )
