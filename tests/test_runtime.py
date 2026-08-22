from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path

from nexora_vpe import DeterministicPhysiologyAdapter, VpeRuntime, load_s0_scenario
from nexora_vpe.model import CommandKind, EventType, RuntimeState
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class CountingDeterministicAdapter(DeterministicPhysiologyAdapter):
    """Test-only adapter that exposes explicit engine-state serialization calls."""

    def __init__(self) -> None:
        super().__init__()
        self.save_state_calls = 0

    def save_state(self):  # type: ignore[no-untyped-def]
        self.save_state_calls += 1
        return super().save_state()


class VpeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = splenic_hemorrhage_learning_scenario()
        self.runtime = VpeRuntime(self.scenario, DeterministicPhysiologyAdapter())
        self.runtime.start()

    def test_versioned_source_scenario_loads_and_is_learning_mode_only(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        loaded = load_s0_scenario(project_root / "scenarios" / "trauma_splenic_01.json")
        self.assertEqual("trauma_splenic_01", loaded.scenario_id)
        self.assertEqual("1.2", loaded.schema_version)
        self.assertEqual("learning", loaded.mode)
        self.assertEqual("Spleen", loaded.hemorrhage_compartment)
        self.assertEqual(
            ("identify_deterioration", "suspect_internal_bleeding", "request_fast", "begin_resuscitation", "reassess"),
            loaded.learning_objectives,
        )
        self.assertEqual(frozenset({"INTERNAL_BLEEDING"}), loaded.allowed_clinical_hypotheses)
        self.assertEqual(frozenset({"VITALS", "FAST"}), loaded.allowed_observation_ids())
        self.assertEqual("free_fluid_positive", loaded.observations["FAST"].controlled_finding)
        self.assertEqual("Abdominal trauma", loaded.client_title)
        self.assertEqual(
            ("heart_rate_bpm", "mean_arterial_pressure_mmhg", "oxygen_saturation"),
            loaded.learner_visible_telemetry,
        )
        self.assertEqual((), loaded.completion_success_rules)
        self.assertEqual((), loaded.completion_failure_rules)
        self.assertIn("blood_packed_rbc", loaded.interventions)
        self.assertIn("trauma_team_escalation", loaded.escalations)

    def test_scenario_loader_rejects_unknown_authoritative_field(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        raw = json.loads((project_root / "scenarios" / "trauma_splenic_01.json").read_text(encoding="utf-8"))
        raw["decorative_but_unsupported"] = True
        with tempfile.TemporaryDirectory() as directory:
            invalid_path = Path(directory) / "invalid.json"
            invalid_path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid S0 scenario contract"):
                load_s0_scenario(invalid_path)

    def test_scenario_loader_rejects_malformed_authoritative_values(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source = project_root / "scenarios" / "trauma_splenic_01.json"
        cases = {
            "learning_objectives_type": lambda raw: raw.__setitem__("learning_objectives", "identify_deterioration"),
            "telemetry_item_type": lambda raw: raw.__setitem__("telemetry", ["heart_rate_bpm", 7]),
            "history_intent_type": lambda raw: raw["history"].__setitem__("allowed_intents", ["PAIN_ONSET", 7]),
            "clinical_hypothesis_type": lambda raw: raw["clinical_hypotheses"].__setitem__("allowed", ["INTERNAL_BLEEDING", 7]),
            "observation_finding_type": lambda raw: raw["observations"]["allowed"][0].__setitem__("controlled_finding", 7),
            "intervention_number_type": lambda raw: raw["interventions"]["allowed"][0].__setitem__("volume_ml", "500"),
            "duplicate_observation_id": lambda raw: raw["observations"]["allowed"].append(dict(raw["observations"]["allowed"][0])),
            "hidden_client_telemetry": lambda raw: raw["client_view"].__setitem__("visible_telemetry", ["blood_volume_ml"]),
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, mutate in cases.items():
                with self.subTest(name=name):
                    raw = json.loads(source.read_text(encoding="utf-8"))
                    mutate(raw)
                    invalid_path = Path(directory) / f"{name}.json"
                    invalid_path.write_text(json.dumps(raw), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Invalid S0 scenario contract"):
                        load_s0_scenario(invalid_path)

    def test_scenario_schema_covers_source_authoritative_fields(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        raw = json.loads((project_root / "scenarios" / "trauma_splenic_01.json").read_text(encoding="utf-8"))
        schema = json.loads((project_root / "schemas" / "s0-scenario.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(raw), set(schema["required"]))
        self.assertEqual(set(raw), set(schema["properties"]))
        self.assertEqual(
            set(raw["observations"]),
            set(schema["properties"]["observations"]["required"]),
        )
        self.assertEqual(
            set(raw["clinical_hypotheses"]),
            set(schema["properties"]["clinical_hypotheses"]["required"]),
        )

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

    def test_clinical_hypothesis_is_distinct_from_history_intent(self) -> None:
        self.runtime.submit(
            CommandKind.RECORD_CLINICAL_HYPOTHESIS,
            "learner",
            {"hypothesis_id": "INTERNAL_BLEEDING"},
        )
        events = self.runtime.drain()
        self.assertEqual(EventType.CLINICAL_HYPOTHESIS_RECORDED, events[0].event_type)
        self.assertEqual("INTERNAL_BLEEDING", events[0].payload["hypothesis_id"])

        self.runtime.submit(
            CommandKind.RECORD_HISTORY_INTENT,
            "learner",
            {"intent_id": "SUSPECT_INTERNAL_BLEEDING"},
        )
        with self.assertRaisesRegex(ValueError, "History intent is not allowed by scenario"):
            self.runtime.drain()

    def test_observation_allowlist_comes_from_scenario_contract(self) -> None:
        self.runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "VITALS"})
        self.runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "FAST"})
        events = self.runtime.drain()
        requested = [event.payload["observation_id"] for event in events]
        self.assertEqual(["VITALS", "FAST"], requested)

        self.runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "CBC"})
        with self.assertRaisesRegex(ValueError, "Observation is not allowed by scenario"):
            self.runtime.drain()

    def test_non_physiology_actions_do_not_advance_simulation_time(self) -> None:
        self.runtime.submit(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "PAIN_LOCATION"})
        self.runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "FAST"})
        self.runtime.drain()
        self.assertEqual(0.0, self.runtime.simulation_time_s)

    def test_records_scenario_authorized_escalation_without_mutating_physiology(self) -> None:
        before_snapshot_count = len(self.runtime.snapshots())
        self.runtime.submit(
            CommandKind.RECORD_ESCALATION,
            "learner",
            {"escalation_id": "trauma_team_escalation"},
        )
        new_events = self.runtime.drain()

        self.assertEqual(1, len(new_events))
        event = new_events[0]
        self.assertEqual(EventType.ESCALATION_RECORDED, event.event_type)
        self.assertEqual("scenario_runtime", event.source)
        self.assertEqual("trauma_team_escalation", event.payload["escalation_id"])
        self.assertEqual(0.0, event.simulation_time_s)
        self.assertEqual(0.0, self.runtime.simulation_time_s)
        self.assertEqual(before_snapshot_count, len(self.runtime.snapshots()))

    def test_rejects_unapproved_escalation(self) -> None:
        self.runtime.submit(
            CommandKind.RECORD_ESCALATION,
            "learner",
            {"escalation_id": "unapproved_destination"},
        )
        with self.assertRaisesRegex(ValueError, "Escalation not allowed by scenario"):
            self.runtime.drain()

    def test_queue_failure_retains_unprocessed_commands_in_order(self) -> None:
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 1.0})
        self.runtime.submit(
            CommandKind.APPLY_INTERVENTION,
            "learner",
            {"intervention_id": "unknown_intervention"},
        )
        retained_id = self.runtime.submit(
            CommandKind.RECORD_HISTORY_INTENT,
            "learner",
            {"intent_id": "PAIN_ONSET"},
        )

        with self.assertRaisesRegex(ValueError, "Intervention not allowed by scenario"):
            self.runtime.drain()

        meaningful = [event for event in self.runtime.events() if event.event_type != EventType.SNAPSHOT_PUBLISHED]
        self.assertEqual([EventType.CLOCK_ADVANCED], [event.event_type for event in meaningful])
        self.assertEqual(1.0, self.runtime.simulation_time_s)
        self.assertEqual((retained_id,), self.runtime.queued_command_ids())

        retained_events = self.runtime.drain()
        self.assertEqual(EventType.CLINICAL_INTENT_RECORDED, retained_events[0].event_type)
        self.assertEqual((), self.runtime.queued_command_ids())

    def test_invalid_actor_cannot_mutate_intervention_or_advance(self) -> None:
        initial_event_count = len(self.runtime.events())
        initial_snapshot_count = len(self.runtime.snapshots())

        self.runtime.submit(
            CommandKind.APPLY_INTERVENTION,
            "untrusted_actor",
            {"intervention_id": "crystalloid_saline"},
        )
        with self.assertRaisesRegex(ValueError, "Event actor is not permitted"):
            self.runtime.drain()
        self.assertEqual(0.0, self.runtime.simulation_time_s)
        self.assertEqual(initial_event_count, len(self.runtime.events()))
        self.assertEqual(initial_snapshot_count, len(self.runtime.snapshots()))

        self.runtime.submit(CommandKind.ADVANCE_TIME, "untrusted_actor", {"duration_s": 30.0})
        with self.assertRaisesRegex(ValueError, "Event actor is not permitted"):
            self.runtime.drain()
        self.assertEqual(0.0, self.runtime.simulation_time_s)
        self.assertEqual(initial_event_count, len(self.runtime.events()))
        self.assertEqual(initial_snapshot_count, len(self.runtime.snapshots()))

    def test_malformed_payload_or_unknown_intervention_cannot_mutate_physiology(self) -> None:
        initial_event_count = len(self.runtime.events())
        initial_snapshot_count = len(self.runtime.snapshots())
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": float("nan")})
        with self.assertRaisesRegex(ValueError, "positive finite duration_s"):
            self.runtime.drain()
        self.assertEqual(0.0, self.runtime.simulation_time_s)

        self.runtime.submit(
            CommandKind.APPLY_INTERVENTION,
            "learner",
            {"intervention_id": "unknown_intervention"},
        )
        with self.assertRaisesRegex(ValueError, "Intervention not allowed by scenario"):
            self.runtime.drain()
        self.assertEqual(0.0, self.runtime.simulation_time_s)
        self.assertEqual(initial_event_count, len(self.runtime.events()))
        self.assertEqual(initial_snapshot_count, len(self.runtime.snapshots()))

    def test_duplicate_side_effecting_request_executes_once_and_returns_existing_outcome(self) -> None:
        request_id = "ui.advance.001"
        first_id = self.runtime.submit(
            CommandKind.ADVANCE_TIME,
            "learner",
            {"duration_s": 30.0},
            request_id=request_id,
        )
        duplicate_id = self.runtime.submit(
            CommandKind.ADVANCE_TIME,
            "learner",
            {"duration_s": 30.0},
            request_id=request_id,
        )
        self.assertEqual(first_id, duplicate_id)
        self.assertEqual((first_id,), self.runtime.queued_command_ids())

        first_outcome = self.runtime.drain()
        self.assertEqual(30.0, self.runtime.simulation_time_s)
        self.assertEqual(first_outcome, self.runtime.request_outcome(request_id))

        repeated_id = self.runtime.submit(
            CommandKind.ADVANCE_TIME,
            "learner",
            {"duration_s": 30.0},
            request_id=request_id,
        )
        self.assertEqual(first_id, repeated_id)
        self.assertEqual((), self.runtime.queued_command_ids())
        self.assertEqual(30.0, self.runtime.simulation_time_s)

        with self.assertRaisesRegex(ValueError, "already bound to a different command"):
            self.runtime.submit(
                CommandKind.ADVANCE_TIME,
                "learner",
                {"duration_s": 60.0},
                request_id=request_id,
            )

    def test_only_explicit_checkpoint_serializes_engine_state(self) -> None:
        adapter = CountingDeterministicAdapter()
        runtime = VpeRuntime(splenic_hemorrhage_learning_scenario(), adapter)
        runtime.start()
        self.assertEqual(0, adapter.save_state_calls)
        self.assertNotIn("adapter_state", runtime.snapshots()[-1].as_dict())

        runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 10.0})
        runtime.drain()
        self.assertEqual(0, adapter.save_state_calls)

        runtime.submit(
            CommandKind.APPLY_INTERVENTION,
            "learner",
            {"intervention_id": "crystalloid_saline"},
        )
        runtime.drain()
        self.assertEqual(0, adapter.save_state_calls)

        runtime.submit(CommandKind.CREATE_CHECKPOINT, "learner", {"checkpoint_id": "explicit"})
        runtime.drain()
        self.assertEqual(1, adapter.save_state_calls)
        artifacts = runtime.checkpoint_artifacts()
        self.assertEqual(1, len(artifacts))
        self.assertEqual("explicit", artifacts[0].checkpoint_id)
        self.assertEqual(runtime.simulation_time_s, artifacts[0].simulation_time_s)

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
