from __future__ import annotations

import unittest

from pathlib import Path

from nexora_vpe import DeterministicPhysiologyAdapter, VpeRuntime, load_s0_scenario
from nexora_vpe.model import CommandKind, EventType, RuntimeState
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class VpeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = splenic_hemorrhage_learning_scenario()
        self.runtime = VpeRuntime(self.scenario, DeterministicPhysiologyAdapter())
        self.runtime.start()

    def test_versioned_source_scenario_loads_and_is_learning_mode_only(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        loaded = load_s0_scenario(project_root / "scenarios" / "trauma_splenic_01.json")
        self.assertEqual("trauma_splenic_01", loaded.scenario_id)
        self.assertEqual("learning", loaded.mode)
        self.assertEqual("Spleen", loaded.hemorrhage_compartment)
        self.assertIn("blood_packed_rbc", loaded.interventions)

    def test_start_bootstraps_existing_pathology_and_publishes_snapshot(self) -> None:
        self.assertEqual(RuntimeState.RUNNING, self.runtime.state)
        snapshots = self.runtime.snapshots()
        self.assertEqual(1, len(snapshots))
        self.assertEqual(0.0, snapshots[0].simulation_time_s)
        self.assertEqual("scenario_started", snapshots[0].reason)
        self.assertEqual("deterministic-test-double/1.0", snapshots[0].engine_version)

    def test_command_submission_order_is_preserved(self) -> None:
        self.runtime.submit(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "PAIN_ONSET"})
        self.runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "VITALS"})
        new_events = self.runtime.drain()
        meaningful = [event for event in new_events if event.event_type != EventType.SNAPSHOT_PUBLISHED]
        self.assertEqual(
            [EventType.CLINICAL_INTENT_RECORDED, EventType.OBSERVATION_REQUESTED],
            [event.event_type for event in meaningful],
        )
        self.assertEqual("PAIN_ONSET", meaningful[0].payload["intent_id"])
        self.assertEqual("VITALS", meaningful[1].payload["observation_id"])

    def test_non_physiology_actions_do_not_advance_simulation_time(self) -> None:
        self.runtime.submit(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "PAIN_LOCATION"})
        self.runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "FAST"})
        self.runtime.drain()
        self.assertEqual(0.0, self.runtime.simulation_time_s)

    def test_intervention_then_time_advance_publishes_ordered_evidence(self) -> None:
        self.runtime.submit(CommandKind.APPLY_INTERVENTION, "learner", {"intervention_id": "crystalloid_saline"})
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        events = self.runtime.events()
        types = [event.event_type for event in events]
        self.assertIn(EventType.INTERVENTION_APPLIED, types)
        self.assertIn(EventType.CLOCK_ADVANCED, types)
        self.assertEqual(60.0, self.runtime.simulation_time_s)
        latest = self.runtime.snapshots()[-1]
        self.assertEqual("time_advanced", latest.reason)
        self.assertGreater(latest.telemetry["total_hemorrhaged_volume_ml"], 0.0)

    def test_checkpoint_restore_reproduces_saved_telemetry_and_marks_branch(self) -> None:
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 90.0})
        self.runtime.submit(CommandKind.CREATE_CHECKPOINT, "learner", {"checkpoint_id": "after_90"})
        self.runtime.drain()
        saved = self.runtime.snapshots()[-1]
        self.assertEqual("checkpoint:after_90", saved.reason)

        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 30.0})
        self.runtime.drain()
        self.assertEqual(120.0, self.runtime.simulation_time_s)

        self.runtime.submit(CommandKind.RESTORE_CHECKPOINT, "learner", {"checkpoint_id": "after_90"})
        self.runtime.drain()
        restored = self.runtime.snapshots()[-1]
        self.assertEqual(90.0, self.runtime.simulation_time_s)
        self.assertEqual("checkpoint_restored:after_90", restored.reason)
        self.assertEqual(dict(saved.telemetry), dict(restored.telemetry))
        self.assertEqual(EventType.CHECKPOINT_RESTORED, self.runtime.events()[-2].event_type)

    def test_rejects_unapproved_intent_and_intervention(self) -> None:
        self.runtime.submit(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "UNSAFE_FREE_TEXT"})
        with self.assertRaises(ValueError):
            self.runtime.drain()

        self.runtime.submit(CommandKind.APPLY_INTERVENTION, "learner", {"intervention_id": "arbitrary_drug"})
        with self.assertRaises(ValueError):
            self.runtime.drain()

    def test_completion_requires_drained_queue(self) -> None:
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 1.0})
        with self.assertRaises(RuntimeError):
            self.runtime.complete()
        self.runtime.drain()
        self.runtime.complete()
        self.assertEqual(RuntimeState.COMPLETED, self.runtime.state)


if __name__ == "__main__":
    unittest.main()
