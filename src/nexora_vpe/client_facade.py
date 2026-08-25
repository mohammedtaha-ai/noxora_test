"""Headless learner-safe boundary around :class:`VpeRuntime`.

The facade is intentionally the only client-facing surface.  It projects
scenario/state/event data into explicit DTOs and never returns runtime snapshots,
checkpoint artifacts, adapter state, or full scenario definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .client_contracts import (
    ClientCommandStatus,
    ClientError,
    ClientErrorCode,
    ClientEvent,
    ClientRuntimeState,
    ClientScenarioManifest,
    ClientSnapshot,
    CommandAccepted,
    CommandOutcome,
    CommandRequest,
)
from .model import CommandKind, Event, EventType
from .runtime import VpeRuntime


_CLIENT_COMMAND_KINDS = frozenset(
    {
        CommandKind.RECORD_HISTORY_INTENT,
        CommandKind.RECORD_CLINICAL_HYPOTHESIS,
        CommandKind.REQUEST_OBSERVATION,
        CommandKind.RECORD_ESCALATION,
        CommandKind.APPLY_INTERVENTION,
    }
)


@dataclass
class VpeClientFacade:
    """Project a running VPE Runtime into a learner-safe local contract.

    The VPE host, not the client, calls :meth:`process_pending`.  In particular,
    `advance_time`, checkpoint creation, and checkpoint restoration are not
    accepted as learner-client commands.
    """

    runtime: VpeRuntime
    _command_ids: dict[str, str] = field(default_factory=dict)
    _outcomes: dict[str, CommandOutcome] = field(default_factory=dict)

    def scenario_manifest(self) -> ClientScenarioManifest:
        scenario = self.runtime.scenario
        return ClientScenarioManifest(
            scenario_id=scenario.scenario_id,
            title=scenario.client_title,
            mode=scenario.mode,
            allowed_history_intents=tuple(sorted(scenario.allowed_history_intents)),
            allowed_clinical_hypotheses=tuple(sorted(scenario.allowed_clinical_hypotheses)),
            allowed_observation_actions=tuple(sorted(scenario.allowed_observation_ids())),
            allowed_interventions=tuple(sorted(scenario.interventions)),
            allowed_escalations=tuple(sorted(scenario.escalations)),
            visible_telemetry=tuple(scenario.learner_visible_telemetry),
        )

    def current_state(self) -> ClientRuntimeState:
        return ClientRuntimeState(
            runtime_state=self.runtime.state.value,
            simulation_time_s=self.runtime.simulation_time_s,
        )

    def current_snapshot(self) -> ClientSnapshot | None:
        snapshots = self.runtime.snapshots()
        if not snapshots:
            return None
        return self._project_snapshot(snapshots[-1])

    def submit(self, request: CommandRequest) -> CommandAccepted | CommandOutcome:
        """Validate and enqueue a learner action without exposing runtime errors."""
        validation_error = self._validate_client_request(request)
        if validation_error is not None:
            return CommandOutcome(
                request_id=request.request_id,
                command_id=None,
                status=ClientCommandStatus.REJECTED,
                error=validation_error,
            )
        try:
            kind = CommandKind(request.kind)
            command_id = self.runtime.submit(kind, "learner", request.payload, request.request_id)
        except Exception as exc:
            return CommandOutcome(
                request_id=request.request_id,
                command_id=None,
                status=ClientCommandStatus.REJECTED,
                error=self._safe_error(exc),
            )
        self._command_ids[request.request_id] = command_id
        outcome = self._outcomes.get(request.request_id)
        if outcome is not None:
            return outcome
        return CommandAccepted(request_id=request.request_id, command_id=command_id)

    def query_command_outcome(self, request_id: str) -> CommandOutcome:
        """Return a safe outcome without retrying or re-executing any command."""
        known = self._outcomes.get(request_id)
        if known is not None:
            return known
        command_id = self._command_ids.get(request_id)
        if command_id is None:
            return CommandOutcome(
                request_id=request_id,
                command_id=None,
                status=ClientCommandStatus.REJECTED,
                error=ClientError(ClientErrorCode.INVALID_COMMAND, "The request identifier is unknown."),
            )
        events = self.runtime.request_outcome(request_id)
        if events is None:
            return CommandOutcome(
                request_id=request_id,
                command_id=command_id,
                status=ClientCommandStatus.PENDING,
            )
        completed = CommandOutcome(
            request_id=request_id,
            command_id=command_id,
            status=ClientCommandStatus.COMPLETED,
            events=tuple(self._project_event(event) for event in events if self._event_is_client_visible(event)),
        )
        self._outcomes[request_id] = completed
        return completed

    def process_pending(self) -> tuple[CommandOutcome, ...]:
        """Run queued client actions from the VPE host, never from a client clock.

        An exception after command acceptance is marked `AMBIGUOUS`; the facade
        deliberately does not retry because a side effect may already have been
        applied by the physiology adapter.
        """
        pending_before = self.runtime.queued_command_ids()
        if not pending_before:
            return ()
        try:
            self.runtime.drain()
        except Exception as exc:
            remaining = set(self.runtime.queued_command_ids())
            ambiguous_command_id = next((item for item in pending_before if item not in remaining), None)
            if ambiguous_command_id is None:
                return ()
            request_id = self._request_id_for_command(ambiguous_command_id)
            if request_id is None:
                return ()
            outcome = CommandOutcome(
                request_id=request_id,
                command_id=ambiguous_command_id,
                status=ClientCommandStatus.AMBIGUOUS,
                error=self._safe_error(exc, ambiguous=True),
            )
            self._outcomes[request_id] = outcome
            # A side effect may already have reached Pulse. Freeze clinical time
            # until an explicit reconciliation/recovery decision is made.
            if self.runtime.state.value == "RUNNING":
                self.runtime.pause_by_system()
            return (outcome,)
        outcomes: list[CommandOutcome] = []
        for request_id in tuple(self._command_ids):
            outcome = self.query_command_outcome(request_id)
            if outcome.status == ClientCommandStatus.COMPLETED:
                outcomes.append(outcome)
        return tuple(outcomes)

    def new_events(self, after_event_id: str | None = None) -> tuple[ClientEvent, ...]:
        """Return only learner-visible events after an optional visible cursor."""
        visible = tuple(
            self._project_event(event)
            for event in self.runtime.events()
            if self._event_is_client_visible(event)
        )
        if after_event_id is None:
            return visible
        for index, event in enumerate(visible):
            if event.event_id == after_event_id:
                return visible[index + 1 :]
        return visible

    def _validate_client_request(self, request: CommandRequest) -> ClientError | None:
        if not isinstance(request.request_id, str) or not request.request_id:
            return ClientError(ClientErrorCode.INVALID_COMMAND, "A stable request identifier is required.")
        if not isinstance(request.payload, dict):
            return ClientError(ClientErrorCode.INVALID_COMMAND, "The command payload must be an object.")
        try:
            kind = CommandKind(request.kind)
        except (TypeError, ValueError):
            return ClientError(ClientErrorCode.INVALID_COMMAND, "The command kind is not recognized.")
        if kind not in _CLIENT_COMMAND_KINDS:
            return ClientError(ClientErrorCode.NOT_ALLOWED, "This command is not available to the learner client.")
        scenario = self.runtime.scenario
        if kind == CommandKind.RECORD_HISTORY_INTENT:
            if set(request.payload) != {"intent_id"} or request.payload["intent_id"] not in scenario.allowed_history_intents:
                return ClientError(ClientErrorCode.NOT_ALLOWED, "The requested history action is not available.")
        elif kind == CommandKind.RECORD_CLINICAL_HYPOTHESIS:
            if set(request.payload) != {"hypothesis_id"} or request.payload["hypothesis_id"] not in scenario.allowed_clinical_hypotheses:
                return ClientError(ClientErrorCode.NOT_ALLOWED, "The requested clinical hypothesis is not available.")
        elif kind == CommandKind.REQUEST_OBSERVATION:
            if set(request.payload) != {"observation_id"} or request.payload["observation_id"] not in scenario.allowed_observation_ids():
                return ClientError(ClientErrorCode.NOT_ALLOWED, "The requested observation is not available.")
        elif kind == CommandKind.RECORD_ESCALATION:
            if set(request.payload) != {"escalation_id"} or request.payload["escalation_id"] not in scenario.escalations:
                return ClientError(ClientErrorCode.NOT_ALLOWED, "The requested escalation is not available.")
        elif kind == CommandKind.APPLY_INTERVENTION:
            if set(request.payload) != {"intervention_id"} or request.payload["intervention_id"] not in scenario.interventions:
                return ClientError(ClientErrorCode.NOT_ALLOWED, "The requested intervention is not available.")
        return None

    def _project_snapshot(self, snapshot: object) -> ClientSnapshot:
        # Attribute access is deliberate: the internal Snapshot type never crosses
        # the return type, and only the listed public fields are copied.
        telemetry = {
            key: float(getattr(snapshot, "telemetry")[key])
            for key in self.runtime.scenario.learner_visible_telemetry
            if key in getattr(snapshot, "telemetry")
        }
        return ClientSnapshot(
            snapshot_id=str(getattr(snapshot, "snapshot_id")),
            scenario_id=str(getattr(snapshot, "scenario_id")),
            simulation_time_s=float(getattr(snapshot, "simulation_time_s")),
            runtime_state=self.runtime.state.value,
            telemetry=telemetry,
        )

    @staticmethod
    def _event_is_client_visible(event: Event) -> bool:
        return event.event_type in {
            EventType.CLOCK_ADVANCED,
            EventType.CLINICAL_INTENT_RECORDED,
            EventType.CLINICAL_HYPOTHESIS_RECORDED,
            EventType.OBSERVATION_REQUESTED,
            EventType.INTERVENTION_APPLIED,
            EventType.ESCALATION_RECORDED,
        }

    @staticmethod
    def _project_event(event: Event) -> ClientEvent:
        allowed_payload_keys = {
            EventType.CLOCK_ADVANCED: ("duration_s",),
            EventType.CLINICAL_INTENT_RECORDED: ("intent_id",),
            EventType.CLINICAL_HYPOTHESIS_RECORDED: ("hypothesis_id",),
            EventType.OBSERVATION_REQUESTED: ("observation_id",),
            EventType.INTERVENTION_APPLIED: ("intervention_id",),
            EventType.ESCALATION_RECORDED: ("escalation_id",),
        }
        payload = {
            key: event.payload[key]
            for key in allowed_payload_keys.get(event.event_type, ())
            if key in event.payload
        }
        return ClientEvent(
            event_id=event.event_id,
            scenario_id=event.scenario_id,
            simulation_time_s=event.simulation_time_s,
            event_type=event.event_type.value,
            payload=payload,
        )

    def _request_id_for_command(self, command_id: str) -> str | None:
        for request_id, known_command_id in self._command_ids.items():
            if known_command_id == command_id:
                return request_id
        return None

    @staticmethod
    def _safe_error(exc: Exception, ambiguous: bool = False) -> ClientError:
        if ambiguous:
            return ClientError(
                ClientErrorCode.AMBIGUOUS_OUTCOME,
                "The command outcome is ambiguous and must not be retried automatically.",
            )
        if isinstance(exc, RuntimeError):
            return ClientError(ClientErrorCode.INVALID_STATE, "The runtime cannot accept this command now.")
        if isinstance(exc, ValueError) and "request_id is already bound" in str(exc):
            return ClientError(ClientErrorCode.DUPLICATE_REQUEST_CONFLICT, "The request identifier is already in use.")
        return ClientError(ClientErrorCode.INTERNAL_ERROR, "The request could not be processed.")
