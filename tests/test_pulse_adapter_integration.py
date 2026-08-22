"""Integration tests for the production PulseAdapter.

Set PULSE_ROOT to a locally built pinned Pulse installation. The tests use an
engineering simulation only and do not provide clinical advice.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile
import unittest

from nexora_vpe import PulseAdapter, PulseAdapterConfig, VpeRuntime, load_s0_scenario
from nexora_vpe.model import CommandKind, EventType


class PulseAdapterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        pulse_root_text = os.environ.get("PULSE_ROOT")
        if not pulse_root_text:
            raise unittest.SkipTest("PULSE_ROOT is required for Pulse SDK integration tests")
        cls.pulse_root = Path(pulse_root_text).resolve()
        cls.server = Path(
            os.environ.get(
                "PULSE_ADAPTER_SERVER",
                str(cls.project_root / ".build" / "pulse_bridge" / "nexora_pulse_adapter_server"),
            )
        ).resolve()
        cls.working_directory = cls.pulse_root / "bin"
        cls.initial_state = cls.working_directory / "states" / "StandardMale@0s.json"
        missing = [
            path
            for path in (cls.server, cls.working_directory, cls.initial_state)
            if not path.exists()
        ]
        if missing:
            raise unittest.SkipTest(f"Pulse integration prerequisites are unavailable: {missing}")
        cls.scenario_path = cls.project_root / "scenarios" / "trauma_splenic_01.json"

    def setUp(self) -> None:
        self.state_directory = tempfile.TemporaryDirectory(prefix="nexora-pulse-integration-")
        self.adapter = PulseAdapter(
            PulseAdapterConfig(
                server_executable=self.server,
                pulse_working_directory=self.working_directory,
                initial_state_file=self.initial_state,
                state_directory=Path(self.state_directory.name),
                request_timeout_s=30.0,
            )
        )
        self.runtime = VpeRuntime(load_s0_scenario(self.scenario_path), self.adapter)
        self.runtime.start()

    def tearDown(self) -> None:
        self.adapter.close()
        self.state_directory.cleanup()

    def test_runtime_advances_pinned_pulse_and_observes_existing_hemorrhage(self) -> None:
        baseline = self.runtime.snapshots()[-1]
        self.assertEqual("pulse/4.3.2+e8a3649", baseline.engine_version)
        self.assertAlmostEqual(0.0, baseline.simulation_time_s, places=6)
        self.assertAlmostEqual(0.0, baseline.telemetry["total_hemorrhaged_volume_ml"], places=6)

        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 120.0})
        self.runtime.drain()
        advanced = self.runtime.snapshots()[-1]

        self.assertAlmostEqual(120.0, advanced.simulation_time_s, places=6)
        self.assertGreater(
            advanced.telemetry["total_hemorrhaged_volume_ml"],
            baseline.telemetry["total_hemorrhaged_volume_ml"],
        )
        self.assertTrue(all(math.isfinite(value) for value in advanced.telemetry.values()))
        self.assertEqual(EventType.CLOCK_ADVANCED, self.runtime.events()[-2].event_type)

    def test_runtime_applies_constrained_saline_then_tracks_further_time(self) -> None:
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        before_intervention = self.runtime.snapshots()[-1]

        self.runtime.submit(
            CommandKind.APPLY_INTERVENTION,
            "learner",
            {"intervention_id": "crystalloid_saline"},
        )
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        after_intervention = self.runtime.snapshots()[-1]

        event_types = [event.event_type for event in self.runtime.events()]
        self.assertIn(EventType.INTERVENTION_APPLIED, event_types)
        self.assertAlmostEqual(120.0, after_intervention.simulation_time_s, places=6)
        self.assertGreater(
            after_intervention.telemetry["total_hemorrhaged_volume_ml"],
            before_intervention.telemetry["total_hemorrhaged_volume_ml"],
        )
        self.assertTrue(all(math.isfinite(value) for value in after_intervention.telemetry.values()))

    def test_runtime_applies_constrained_packed_rbc_then_tracks_further_time(self) -> None:
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        before_intervention = self.runtime.snapshots()[-1]

        self.runtime.submit(
            CommandKind.APPLY_INTERVENTION,
            "learner",
            {"intervention_id": "blood_packed_rbc"},
        )
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        after_intervention = self.runtime.snapshots()[-1]

        intervention_events = [
            event for event in self.runtime.events() if event.event_type == EventType.INTERVENTION_APPLIED
        ]
        self.assertEqual("PackedRBC", intervention_events[-1].payload["compound"])
        self.assertAlmostEqual(120.0, after_intervention.simulation_time_s, places=6)
        self.assertGreater(
            after_intervention.telemetry["total_hemorrhaged_volume_ml"],
            before_intervention.telemetry["total_hemorrhaged_volume_ml"],
        )
        self.assertTrue(all(math.isfinite(value) for value in after_intervention.telemetry.values()))

    def test_checkpoint_restore_continues_on_the_same_pulse_trajectory(self) -> None:
        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 120.0})
        self.runtime.submit(CommandKind.CREATE_CHECKPOINT, "learner", {"checkpoint_id": "at_120"})
        self.runtime.drain()
        checkpoint = self.runtime.snapshots()[-1]

        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        original_continuation = self.runtime.snapshots()[-1]

        self.runtime.submit(CommandKind.RESTORE_CHECKPOINT, "learner", {"checkpoint_id": "at_120"})
        self.runtime.drain()
        restored = self.runtime.snapshots()[-1]
        self.assertAlmostEqual(checkpoint.simulation_time_s, restored.simulation_time_s, places=6)
        for key in checkpoint.telemetry:
            self.assertAlmostEqual(checkpoint.telemetry[key], restored.telemetry[key], places=6)

        self.runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
        self.runtime.drain()
        replayed_continuation = self.runtime.snapshots()[-1]
        self.assertAlmostEqual(
            original_continuation.simulation_time_s,
            replayed_continuation.simulation_time_s,
            places=6,
        )
        for key in original_continuation.telemetry:
            self.assertAlmostEqual(
                original_continuation.telemetry[key],
                replayed_continuation.telemetry[key],
                places=6,
            )
        self.assertEqual(EventType.CHECKPOINT_RESTORED, self.runtime.events()[-4].event_type)

    def test_adapter_rejects_unconstrained_compound_before_it_reaches_pulse(self) -> None:
        before_time = self.runtime.simulation_time_s
        with self.assertRaises(ValueError):
            self.adapter.apply_intervention(
                {"compound": "ArbitraryCompound", "volume_ml": 1.0, "rate_ml_min": 1.0}
            )
        self.assertAlmostEqual(before_time, self.runtime.simulation_time_s, places=6)


if __name__ == "__main__":
    unittest.main()
