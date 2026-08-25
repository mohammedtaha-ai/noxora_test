from __future__ import annotations

import unittest

from nexora_vpe import (
    ClientCommandStatus,
    CommandRequest,
    DeterministicPhysiologyAdapter,
    VpeClientFacade,
    VpePacedHost,
    VpeRuntime,
)
from nexora_vpe.model import RuntimeState
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class FakeMonotonic:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)
        self.sleeps: list[float] = []

    def now(self) -> float:
        return next(self._values)

    def sleep(self, duration_s: float) -> None:
        self.sleeps.append(duration_s)


class FailingAdvanceAdapter(DeterministicPhysiologyAdapter):
    def advance(self, duration_s: float) -> None:
        raise RuntimeError("synthetic engine failure")


class AmbiguousInterventionAdapter(DeterministicPhysiologyAdapter):
    """Simulate a side effect that may have reached the engine before response loss."""

    def __init__(self) -> None:
        super().__init__()
        self.apply_calls = 0
        self.advance_calls = 0

    def apply_intervention(self, payload: dict[str, object]) -> None:
        self.apply_calls += 1
        super().apply_intervention(payload)
        raise RuntimeError("synthetic response loss after intervention side effect")

    def advance(self, duration_s: float) -> None:
        self.advance_calls += 1
        super().advance(duration_s)


class VpePacedHostTests(unittest.TestCase):
    def _runtime_and_facade(self, adapter: DeterministicPhysiologyAdapter | None = None) -> tuple[VpeRuntime, VpeClientFacade]:
        runtime = VpeRuntime(
            scenario=splenic_hemorrhage_learning_scenario(),
            adapter=adapter or DeterministicPhysiologyAdapter(),
        )
        runtime.start()
        return runtime, VpeClientFacade(runtime)

    def test_paced_host_owns_clock_and_advances_one_bounded_increment(self) -> None:
        runtime, facade = self._runtime_and_facade()
        clock = FakeMonotonic([10.0, 10.05])
        host = VpePacedHost(runtime, facade, tick_simulation_s=0.25, monotonic=clock.now, sleep=clock.sleep)
        result = host.tick_once()
        self.assertEqual(0.25, runtime.simulation_time_s)
        self.assertEqual(0.25, result.advanced_simulation_s)
        self.assertAlmostEqual(0.05, result.wall_elapsed_s)
        self.assertAlmostEqual(0.20, result.slept_s)
        self.assertEqual(1, len(clock.sleeps))
        self.assertAlmostEqual(0.20, clock.sleeps[0])

        rejected = facade.submit(
            CommandRequest(
                kind="advance_time",
                payload={"duration_s": 5.0},
                request_id="learner-may-not-clock",
            )
        )
        self.assertEqual(ClientCommandStatus.REJECTED, rejected.status)
        self.assertEqual(0.25, runtime.simulation_time_s)

    def test_paused_by_system_does_not_advance_simulation(self) -> None:
        runtime, facade = self._runtime_and_facade()
        runtime.pause_by_system()
        host = VpePacedHost(runtime, facade, tick_simulation_s=0.25)
        result = host.tick_once()
        self.assertEqual(RuntimeState.PAUSED_BY_SYSTEM, result.state)
        self.assertEqual(0.0, result.advanced_simulation_s)
        self.assertEqual(0.0, runtime.simulation_time_s)

    def test_overrun_does_not_catch_up_clinical_time(self) -> None:
        runtime, facade = self._runtime_and_facade()
        clock = FakeMonotonic([0.0, 2.0, 2.0, 4.0])
        host = VpePacedHost(runtime, facade, tick_simulation_s=0.25, monotonic=clock.now, sleep=clock.sleep)
        first, second = host.run_ticks(2)
        self.assertEqual(1.75, first.overrun_s)
        self.assertEqual(1.75, second.overrun_s)
        self.assertEqual([], clock.sleeps)
        self.assertEqual(0.5, runtime.simulation_time_s)
        self.assertEqual(0.25, first.advanced_simulation_s)
        self.assertEqual(0.25, second.advanced_simulation_s)

    def test_ambiguous_intervention_pauses_before_host_clock_advance(self) -> None:
        adapter = AmbiguousInterventionAdapter()
        runtime, facade = self._runtime_and_facade(adapter)
        host = VpePacedHost(runtime, facade, tick_simulation_s=0.25, sleep=lambda _: None)
        accepted = facade.submit(
            CommandRequest(
                kind="apply_intervention",
                payload={"intervention_id": "crystalloid_saline"},
                request_id="ambiguous-intervention-001",
            )
        )
        self.assertEqual(ClientCommandStatus.PENDING, facade.query_command_outcome(accepted.request_id).status)

        result = host.tick_once()

        outcome = facade.query_command_outcome("ambiguous-intervention-001")
        self.assertEqual(ClientCommandStatus.AMBIGUOUS, outcome.status)
        self.assertEqual(RuntimeState.PAUSED_BY_SYSTEM, runtime.state)
        self.assertEqual(RuntimeState.PAUSED_BY_SYSTEM, result.state)
        self.assertEqual(0.0, result.advanced_simulation_s)
        self.assertEqual(0.0, runtime.simulation_time_s)
        self.assertEqual(1, adapter.apply_calls)
        self.assertEqual(0, adapter.advance_calls)

        repeated = host.tick_once()
        self.assertEqual(0.0, repeated.advanced_simulation_s)
        self.assertEqual(1, adapter.apply_calls)
        self.assertEqual(0, adapter.advance_calls)

    def test_host_failure_pauses_system_without_advancing_time(self) -> None:
        runtime, facade = self._runtime_and_facade(FailingAdvanceAdapter())
        host = VpePacedHost(runtime, facade, tick_simulation_s=0.25)
        with self.assertRaisesRegex(RuntimeError, "synthetic engine failure"):
            host.tick_once()
        self.assertEqual(RuntimeState.PAUSED_BY_SYSTEM, runtime.state)
        self.assertEqual(0.0, runtime.simulation_time_s)
        with self.assertRaisesRegex(RuntimeError, "Only a running scenario"):
            runtime.pause_by_system()


if __name__ == "__main__":
    unittest.main()
