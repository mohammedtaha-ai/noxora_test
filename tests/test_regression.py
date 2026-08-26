from __future__ import annotations

import unittest

from nexora_vpe.model import Snapshot
from nexora_vpe.regression import comparison_within_tolerance, compare_snapshot_trajectories


class RegressionComparisonTests(unittest.TestCase):
    @staticmethod
    def _snapshot(time_s: float, heart_rate: float) -> Snapshot:
        return Snapshot(
            snapshot_id=f"snp-{time_s}",
            scenario_id="trauma_splenic_01",
            simulation_time_s=time_s,
            engine_version="test-engine/1",
            telemetry={"heart_rate_bpm": heart_rate, "mean_arterial_pressure_mmhg": 80.0},
            reason="time_advanced",
        )

    def test_reports_channel_divergence_within_declared_tolerance(self) -> None:
        baseline = (self._snapshot(10.0, 100.0), self._snapshot(20.0, 110.0))
        repeat = (self._snapshot(10.0, 100.0000000005), self._snapshot(20.0, 110.0))
        comparison = compare_snapshot_trajectories((baseline, repeat), 1e-9)

        self.assertTrue(comparison.comparable)
        self.assertTrue(comparison_within_tolerance(comparison))
        self.assertAlmostEqual(5e-10, comparison.channels["heart_rate_bpm"]["max_abs_divergence"])
        self.assertEqual(2, comparison.channels["heart_rate_bpm"]["comparisons"])

    def test_reports_divergence_outside_declared_tolerance_without_determinism_claim(self) -> None:
        baseline = (self._snapshot(10.0, 100.0),)
        repeat = (self._snapshot(10.0, 100.01),)
        comparison = compare_snapshot_trajectories((baseline, repeat), 1e-9)

        self.assertTrue(comparison.comparable)
        self.assertFalse(comparison_within_tolerance(comparison))
        self.assertFalse(comparison.channels["heart_rate_bpm"]["within_tolerance"])

    def test_rejects_shape_mismatch_as_non_comparable(self) -> None:
        baseline = (self._snapshot(10.0, 100.0),)
        repeat = (self._snapshot(10.0, 100.0), self._snapshot(20.0, 110.0))
        comparison = compare_snapshot_trajectories((baseline, repeat), 0.0)

        self.assertFalse(comparison.comparable)
        self.assertEqual("snapshot_count_mismatch", comparison.reason)
        self.assertFalse(comparison_within_tolerance(comparison))


if __name__ == "__main__":
    unittest.main()
