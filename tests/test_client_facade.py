from __future__ import annotations

import json
import unittest

from nexora_vpe import (
    ClientCommandStatus,
    ClientErrorCode,
    CommandAccepted,
    CommandRequest,
    DeterministicPhysiologyAdapter,
    VpeClientFacade,
    VpeRuntime,
)
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class VpeClientFacadeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = VpeRuntime(
            scenario=splenic_hemorrhage_learning_scenario(),
            adapter=DeterministicPhysiologyAdapter(),
        )
        self.runtime.start()
        self.facade = VpeClientFacade(self.runtime)

    def test_manifest_exposes_capabilities_without_hidden_scenario_truth(self) -> None:
        manifest = self.facade.scenario_manifest().as_dict()
        self.assertEqual("trauma_splenic_01", manifest["scenario_id"])
        self.assertEqual("Abdominal trauma", manifest["title"])
        self.assertEqual("learning", manifest["mode"])
        self.assertEqual(["FAST", "VITALS"], sorted(manifest["allowed_observation_actions"]))
        self.assertEqual(["blood_packed_rbc", "crystalloid_saline"], sorted(manifest["allowed_interventions"]))
        self.assertEqual(["trauma_team_escalation"], manifest["allowed_escalations"])
        self.assertEqual(
            ["heart_rate_bpm", "mean_arterial_pressure_mmhg", "oxygen_saturation"],
            manifest["visible_telemetry"],
        )
        serialized = json.dumps(manifest, sort_keys=True)
        for forbidden in (
            "pathology",
            "existing_internal_hemorrhage",
            "Spleen",
            "free_fluid_positive",
            "pulse_revision",
            "flow_rate",
            "completion",
            "blood_volume",
            "total_hemorrhaged",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_client_snapshot_is_projected_and_never_reuses_internal_snapshot(self) -> None:
        internal = self.runtime.snapshots()[-1]
        client = self.facade.current_snapshot()
        self.assertIsNotNone(client)
        assert client is not None
        self.assertIsNot(client, internal)
        projected = client.as_dict()
        self.assertEqual("RUNNING", projected["runtime_state"])
        self.assertEqual(
            {"heart_rate_bpm", "mean_arterial_pressure_mmhg", "oxygen_saturation"},
            set(projected["telemetry"]),
        )
        serialized = json.dumps(projected, sort_keys=True)
        for forbidden in (
            "blood_volume",
            "total_hemorrhaged",
            "engine_version",
            "reason",
            "adapter_state",
            "checkpoint",
            "engine_state",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_client_can_observe_state_without_invoking_pulse_or_advancing_time(self) -> None:
        before = self.runtime.simulation_time_s
        self.assertIsNotNone(self.facade.current_snapshot())
        self.assertEqual(before, self.facade.current_state().simulation_time_s)
        self.assertEqual(before, self.runtime.simulation_time_s)

    def test_allowed_structured_command_completes_and_events_hide_command_internals(self) -> None:
        accepted = self.facade.submit(
            CommandRequest(
                kind="record_clinical_hypothesis",
                payload={"hypothesis_id": "INTERNAL_BLEEDING"},
                request_id="facade-hypothesis-1",
            )
        )
        self.assertIsInstance(accepted, CommandAccepted)
        processed = self.facade.process_pending()
        self.assertEqual(1, len(processed))
        outcome = self.facade.query_command_outcome("facade-hypothesis-1")
        self.assertEqual(ClientCommandStatus.COMPLETED, outcome.status)
        self.assertEqual("clinical.hypothesis.recorded", outcome.events[0].event_type)
        self.assertEqual({"hypothesis_id": "INTERNAL_BLEEDING"}, dict(outcome.events[0].payload))
        serialized = json.dumps(outcome.as_dict(), sort_keys=True)
        self.assertNotIn("source", serialized)
        self.assertNotIn("actor", serialized)

    def test_duplicate_request_returns_same_command_without_reexecution(self) -> None:
        request = CommandRequest(
            kind="apply_intervention",
            payload={"intervention_id": "crystalloid_saline"},
            request_id="facade-intervention-1",
        )
        first = self.facade.submit(request)
        second = self.facade.submit(request)
        self.assertIsInstance(first, CommandAccepted)
        self.assertIsInstance(second, CommandAccepted)
        assert isinstance(first, CommandAccepted)
        assert isinstance(second, CommandAccepted)
        self.assertEqual(first.command_id, second.command_id)
        self.facade.process_pending()
        events = [event for event in self.facade.new_events() if event.event_type == "intervention.applied"]
        self.assertEqual(1, len(events))

    def test_duplicate_request_conflict_is_safe_and_does_not_expose_runtime_text(self) -> None:
        first = self.facade.submit(
            CommandRequest(
                kind="record_history_intent",
                payload={"intent_id": "PAIN_ONSET"},
                request_id="facade-conflict-1",
            )
        )
        self.assertIsInstance(first, CommandAccepted)
        conflict = self.facade.submit(
            CommandRequest(
                kind="record_history_intent",
                payload={"intent_id": "PAIN_LOCATION"},
                request_id="facade-conflict-1",
            )
        )
        self.assertEqual(ClientCommandStatus.REJECTED, conflict.status)
        assert conflict.error is not None
        self.assertEqual(ClientErrorCode.DUPLICATE_REQUEST_CONFLICT, conflict.error.code)
        serialized = json.dumps(conflict.as_dict(), sort_keys=True)
        for forbidden in ("/home/", "Pulse", "Traceback", "checkpoint", "request_id is already bound"):
            self.assertNotIn(forbidden, serialized)

    def test_unavailable_or_invalid_client_action_has_structured_safe_error(self) -> None:
        rejected = self.facade.submit(
            CommandRequest(
                kind="create_checkpoint",
                payload={"checkpoint_id": "not-client-visible"},
                request_id="facade-checkpoint-1",
            )
        )
        self.assertEqual(ClientCommandStatus.REJECTED, rejected.status)
        assert rejected.error is not None
        self.assertEqual(ClientErrorCode.NOT_ALLOWED, rejected.error.code)
        self.assertNotIn("checkpoint_id", json.dumps(rejected.as_dict(), sort_keys=True))


if __name__ == "__main__":
    unittest.main()
