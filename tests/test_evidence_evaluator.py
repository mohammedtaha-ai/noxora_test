from __future__ import annotations

import unittest

from nexora_vpe import DeterministicPhysiologyAdapter, VpeClientFacade, VpeRuntime, evaluate_evidence
from nexora_vpe.client_contracts import ClientCommandStatus, CommandRequest
from nexora_vpe.model import CommandKind, EventType, RuntimeState
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class FailingInterventionAdapter(DeterministicPhysiologyAdapter):
    def apply_intervention(self, payload):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated post-acceptance adapter response loss")


class EvidenceEvaluatorTests(unittest.TestCase):
    def _runtime(self, adapter: DeterministicPhysiologyAdapter | None = None) -> VpeRuntime:
        runtime = VpeRuntime(splenic_hemorrhage_learning_scenario(), adapter or DeterministicPhysiologyAdapter())
        runtime.start()
        return runtime

    @staticmethod
    def _apply(runtime: VpeRuntime, kind: CommandKind, payload: dict[str, object]) -> None:
        runtime.submit(kind, "learner", payload)
        runtime.drain()

    @staticmethod
    def _finding(result, dimension_id: str):  # type: ignore[no-untyped-def]
        return next(finding for finding in result.findings if finding.dimension_id == dimension_id)

    def test_competent_trajectory_has_exact_formative_evidence_without_score(self) -> None:
        runtime = self._runtime()
        for intent_id in ("PAIN_ONSET", "PAIN_LOCATION", "MECHANISM_OF_INJURY"):
            self._apply(runtime, CommandKind.RECORD_HISTORY_INTENT, {"intent_id": intent_id})
        self._apply(runtime, CommandKind.REQUEST_OBSERVATION, {"observation_id": "VITALS"})
        self._apply(
            runtime,
            CommandKind.RECORD_CLINICAL_HYPOTHESIS,
            {"hypothesis_id": "INTERNAL_BLEEDING"},
        )
        self._apply(runtime, CommandKind.REQUEST_OBSERVATION, {"observation_id": "FAST"})
        self._apply(runtime, CommandKind.ADVANCE_TIME, {"duration_s": 60.0})
        self._apply(
            runtime,
            CommandKind.APPLY_INTERVENTION,
            {"intervention_id": "crystalloid_saline"},
        )
        self._apply(runtime, CommandKind.ADVANCE_TIME, {"duration_s": 30.0})
        self._apply(runtime, CommandKind.REQUEST_OBSERVATION, {"observation_id": "VITALS"})
        self._apply(
            runtime,
            CommandKind.RECORD_ESCALATION,
            {"escalation_id": "trauma_team_escalation"},
        )

        result = evaluate_evidence(runtime.events(), runtime.snapshots())
        expected_present = {
            "deterioration_observation",
            "internal_bleeding_hypothesis",
            "fast_request",
            "resuscitation",
            "reassessment",
            "escalation",
        }
        self.assertEqual("1.0", result.schema_version)
        self.assertEqual("trauma_splenic_01", result.scenario_id)
        self.assertEqual((), result.session_markers)
        for dimension_id in expected_present:
            self.assertEqual("EVIDENCE_PRESENT", self._finding(result, dimension_id).status.value)
        fast_acquisition = self._finding(result, "fast_acquisition")
        self.assertEqual("UNMEASURABLE", fast_acquisition.status.value)
        self.assertFalse(fast_acquisition.out_of_scope)
        self.assertEqual(
            ("fast.acquisition.recorded:RESERVED_UNTIL_M4",),
            fast_acquisition.missing_signals,
        )
        self.assertNotIn("score", result.as_dict())
        self.assertNotIn("pass", result.as_dict())

    def test_delayed_resuscitation_remains_timed_evidence_not_a_grade(self) -> None:
        runtime = self._runtime()
        self._apply(runtime, CommandKind.ADVANCE_TIME, {"duration_s": 120.0})
        self._apply(
            runtime,
            CommandKind.APPLY_INTERVENTION,
            {"intervention_id": "blood_packed_rbc"},
        )

        result = evaluate_evidence(runtime.events(), runtime.snapshots())
        finding = self._finding(result, "resuscitation")
        self.assertEqual("EVIDENCE_PRESENT", finding.status.value)
        event = next(event for event in runtime.events() if event.event_id == finding.event_ids[0])
        self.assertEqual(EventType.INTERVENTION_APPLIED, event.event_type)
        self.assertEqual(120.0, event.simulation_time_s)
        self.assertEqual("UNMEASURABLE", self._finding(result, "reassessment").status.value)

    def test_reserved_fast_acquisition_is_unmeasurable_and_not_emitted_by_current_producers(self) -> None:
        runtime = self._runtime()
        self._apply(runtime, CommandKind.REQUEST_OBSERVATION, {"observation_id": "FAST"})
        self._apply(runtime, CommandKind.ADVANCE_TIME, {"duration_s": 30.0})

        self.assertNotIn("record_fast_acquisition", {kind.value for kind in CommandKind})
        self.assertNotIn(
            EventType.FAST_ACQUISITION_RECORDED,
            {event.event_type for event in runtime.events()},
        )
        finding = self._finding(evaluate_evidence(runtime.events(), runtime.snapshots()), "fast_acquisition")
        self.assertEqual("UNMEASURABLE", finding.status.value)
        self.assertFalse(finding.out_of_scope)
        self.assertEqual(
            ("fast.acquisition.recorded:RESERVED_UNTIL_M4",),
            finding.missing_signals,
        )

    def test_no_fast_emits_explicit_unmeasurable_signal(self) -> None:
        runtime = self._runtime()
        self._apply(runtime, CommandKind.REQUEST_OBSERVATION, {"observation_id": "VITALS"})
        self._apply(runtime, CommandKind.ADVANCE_TIME, {"duration_s": 30.0})
        result = evaluate_evidence(runtime.events(), runtime.snapshots())

        finding = self._finding(result, "fast_request")
        self.assertEqual("UNMEASURABLE", finding.status.value)
        self.assertEqual(("observation.requested:FAST",), finding.missing_signals)

    def test_no_reassessment_emits_explicit_unmeasurable_signal(self) -> None:
        runtime = self._runtime()
        self._apply(
            runtime,
            CommandKind.APPLY_INTERVENTION,
            {"intervention_id": "crystalloid_saline"},
        )
        self._apply(runtime, CommandKind.ADVANCE_TIME, {"duration_s": 30.0})
        result = evaluate_evidence(runtime.events(), runtime.snapshots())

        finding = self._finding(result, "reassessment")
        self.assertEqual("UNMEASURABLE", finding.status.value)
        self.assertEqual(("observation.requested:after_intervention",), finding.missing_signals)

    def test_ambiguous_command_pause_is_recorded_in_evidence_stream(self) -> None:
        runtime = self._runtime(FailingInterventionAdapter())
        facade = VpeClientFacade(runtime)
        accepted = facade.submit(
            CommandRequest(
                request_id="ambiguous.intervention.001",
                kind=CommandKind.APPLY_INTERVENTION.value,
                payload={"intervention_id": "crystalloid_saline"},
            )
        )
        self.assertEqual("cmd-000001", accepted.command_id)

        outcomes = facade.process_pending()
        self.assertEqual(1, len(outcomes))
        self.assertEqual(ClientCommandStatus.AMBIGUOUS, outcomes[0].status)
        self.assertEqual(RuntimeState.PAUSED_BY_SYSTEM, runtime.state)
        self.assertEqual(
            EventType.RUNTIME_PAUSED_BY_SYSTEM,
            runtime.events()[-1].event_type,
        )
        self.assertEqual("ambiguous_command_outcome", runtime.events()[-1].payload["reason"])

        result = evaluate_evidence(runtime.events(), runtime.snapshots())
        self.assertEqual(("PAUSED_BY_SYSTEM",), tuple(marker.marker_id for marker in result.session_markers))
        self.assertEqual((runtime.events()[-1].event_id,), result.session_markers[0].event_ids)


if __name__ == "__main__":
    unittest.main()
