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
