"""Deterministic, formative-only evaluation of recorded S0 evidence.

This module consumes canonical events and snapshots already committed by ``VpeRuntime``.
It never calls an adapter, advances simulation time, performs network I/O, or returns a
score, rank, pass/fail decision, or clinical recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Iterable, Sequence

from .model import Event, EventType, Snapshot


EVALUATOR_SCHEMA_VERSION = "1.0"


class FindingStatus(str, Enum):
    """Non-judgmental evidence availability states for Learning Mode."""

    EVIDENCE_PRESENT = "EVIDENCE_PRESENT"
    UNMEASURABLE = "UNMEASURABLE"


@dataclass(frozen=True)
class EvidenceFinding:
    """A structured, non-scored finding for one S0 formative dimension."""

    dimension_id: str
    rubric_dimension: str
    status: FindingStatus
    event_ids: tuple[str, ...]
    snapshot_ids: tuple[str, ...]
    missing_signals: tuple[str, ...] = ()
    out_of_scope: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "rubric_dimension": self.rubric_dimension,
            "status": self.status.value,
            "event_ids": list(self.event_ids),
            "snapshot_ids": list(self.snapshot_ids),
            "missing_signals": list(self.missing_signals),
            "out_of_scope": self.out_of_scope,
        }


@dataclass(frozen=True)
class SessionMarker:
    """Operational replay context that is deliberately not a learner grade."""

    marker_id: str
    event_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"marker_id": self.marker_id, "event_ids": list(self.event_ids)}


@dataclass(frozen=True)
class EvaluationResult:
    """Deterministic evaluator result for one canonical recorded session."""

    schema_version: str
    scenario_id: str
    findings: tuple[EvidenceFinding, ...]
    session_markers: tuple[SessionMarker, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "findings": [finding.as_dict() for finding in self.findings],
            "session_markers": [marker.as_dict() for marker in self.session_markers],
        }


def evaluate_evidence(events: Sequence[Event], snapshots: Sequence[Snapshot]) -> EvaluationResult:
    """Evaluate recorded evidence without re-running physiology or using wall time.

    The result intentionally records missing signals as ``UNMEASURABLE``. It does
    not infer an omitted learner action, and it does not interpret the stream as a
    clinical score.
    """

    scenario_id = _single_scenario_id(events, snapshots)
    snapshot_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}

    vitals_events = _matching(events, EventType.OBSERVATION_REQUESTED, "observation_id", "VITALS")
    published_snapshot_events = _matching(events, EventType.SNAPSHOT_PUBLISHED)
    referenced_snapshots = tuple(
        snapshot_by_id[str(event.payload["snapshot_id"])]
        for event in published_snapshot_events
        if isinstance(event.payload.get("snapshot_id"), str)
        and str(event.payload["snapshot_id"]) in snapshot_by_id
    )
    deterioration_is_measurable = bool(vitals_events) and len(referenced_snapshots) >= 2
    deterioration_missing: list[str] = []
    if not vitals_events:
        deterioration_missing.append("observation.requested:VITALS")
    if len(referenced_snapshots) < 2:
        deterioration_missing.append("snapshot.published:at_least_two")

    hypothesis_events = _matching(
        events,
        EventType.CLINICAL_HYPOTHESIS_RECORDED,
        "hypothesis_id",
        "INTERNAL_BLEEDING",
    )
    fast_events = _matching(events, EventType.OBSERVATION_REQUESTED, "observation_id", "FAST")
    fast_acquisition_events = _matching(events, EventType.FAST_ACQUISITION_RECORDED)
    intervention_events = _matching(events, EventType.INTERVENTION_APPLIED)
    escalation_events = _matching(events, EventType.ESCALATION_RECORDED)
    reassessment_events = _observations_after_intervention(events, intervention_events)
    system_pause_events = _matching(events, EventType.RUNTIME_PAUSED_BY_SYSTEM)

    findings = (
        _finding(
            "deterioration_observation",
            "ملاحظة التدهور",
            deterioration_is_measurable,
            vitals_events,
            referenced_snapshots,
            tuple(deterioration_missing),
        ),
        _finding(
            "internal_bleeding_hypothesis",
            "اشتباه النزف الداخلي",
            bool(hypothesis_events),
            hypothesis_events,
            (),
            ("clinical.hypothesis.recorded:INTERNAL_BLEEDING",),
        ),
        _finding(
            "fast_request",
            "تسلسل FAST: طلب الدليل",
            bool(fast_events),
            fast_events,
            (),
            ("observation.requested:FAST",),
        ),
        _finding(
            "fast_acquisition",
            "تسلسل FAST: اكتساب صالح",
            bool(fast_acquisition_events),
            fast_acquisition_events,
            (),
            ("fast.acquisition.recorded:RESERVED_UNTIL_M4",),
        ),
        _finding(
            "resuscitation",
            "الإنعاش",
            bool(intervention_events),
            intervention_events,
            (),
            ("intervention.applied",),
        ),
        _finding(
            "reassessment",
            "إعادة التقييم",
            bool(reassessment_events),
            reassessment_events,
            (),
            ("observation.requested:after_intervention",),
        ),
        _finding(
            "escalation",
            "التصعيد",
            bool(escalation_events),
            escalation_events,
            (),
            ("escalation.recorded",),
        ),
    )
    markers = ()
    if system_pause_events:
        markers = (SessionMarker("PAUSED_BY_SYSTEM", tuple(event.event_id for event in system_pause_events)),)
    return EvaluationResult(
        schema_version=EVALUATOR_SCHEMA_VERSION,
        scenario_id=scenario_id,
        findings=findings,
        session_markers=markers,
    )


def serialize_evaluation(result: EvaluationResult) -> str:
    """Return byte-stable JSON for replay-equivalence assertions and artifacts."""

    return json.dumps(result.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _single_scenario_id(events: Sequence[Event], snapshots: Sequence[Snapshot]) -> str:
    scenario_ids = {event.scenario_id for event in events} | {snapshot.scenario_id for snapshot in snapshots}
    if len(scenario_ids) != 1:
        raise ValueError("Recorded evidence must belong to exactly one scenario")
    return next(iter(scenario_ids))


def _matching(
    events: Iterable[Event],
    event_type: EventType,
    payload_key: str | None = None,
    expected_value: object | None = None,
) -> tuple[Event, ...]:
    matches: list[Event] = []
    for event in events:
        if event.event_type != event_type:
            continue
        if payload_key is not None and event.payload.get(payload_key) != expected_value:
            continue
        matches.append(event)
    return tuple(matches)


def _observations_after_intervention(events: Sequence[Event], interventions: Sequence[Event]) -> tuple[Event, ...]:
    if not interventions:
        return ()
    last_intervention_index = max(index for index, event in enumerate(events) if event in interventions)
    last_intervention_time = events[last_intervention_index].simulation_time_s
    return tuple(
        event
        for event in events[last_intervention_index + 1 :]
        if event.event_type == EventType.OBSERVATION_REQUESTED
        and event.simulation_time_s >= last_intervention_time
    )


def _finding(
    dimension_id: str,
    rubric_dimension: str,
    evidence_present: bool,
    events: Sequence[Event],
    snapshots: Sequence[Snapshot],
    missing_signals: tuple[str, ...],
    *,
    out_of_scope: bool = False,
) -> EvidenceFinding:
    return EvidenceFinding(
        dimension_id=dimension_id,
        rubric_dimension=rubric_dimension,
        status=FindingStatus.EVIDENCE_PRESENT if evidence_present else FindingStatus.UNMEASURABLE,
        event_ids=tuple(event.event_id for event in events),
        snapshot_ids=tuple(snapshot.snapshot_id for snapshot in snapshots),
        missing_signals=() if evidence_present else missing_signals,
        out_of_scope=out_of_scope,
    )
