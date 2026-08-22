"""VPE-owned paced host loop for S0 Learning Mode.

A learner client can submit structured actions through the facade, but it never
owns simulation-clock progression.  The host uses a monotonic wall clock only
for pacing; any overrun is recorded and skipped rather than converted into a
catch-up burst of clinical time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable

from .client_facade import VpeClientFacade
from .model import CommandKind, RuntimeState
from .runtime import VpeRuntime


@dataclass(frozen=True)
class TickResult:
    tick_index: int
    advanced_simulation_s: float
    wall_elapsed_s: float
    slept_s: float
    overrun_s: float
    state: RuntimeState


@dataclass
class VpePacedHost:
    """Advance an already-running runtime in bounded, host-owned increments."""

    runtime: VpeRuntime
    facade: VpeClientFacade
    tick_simulation_s: float = 0.25
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _tick_index: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.facade.runtime is not self.runtime:
            raise ValueError("Host and facade must reference the same runtime")
        if self.tick_simulation_s <= 0:
            raise ValueError("tick_simulation_s must be positive")

    def tick_once(self) -> TickResult:
        """Process learner actions and advance exactly one bounded S0 tick.

        If the runtime is paused or complete, it does not advance time.  If the
        tick itself overruns, the next tick remains exactly one increment: no
        wall-time catch-up is applied.
        """
        if self.runtime.state != RuntimeState.RUNNING:
            return TickResult(
                tick_index=self._tick_index,
                advanced_simulation_s=0.0,
                wall_elapsed_s=0.0,
                slept_s=0.0,
                overrun_s=0.0,
                state=self.runtime.state,
            )
        started = self.monotonic()
        try:
            self.facade.process_pending()
            # The host, not a learner request, owns every ADVANCE_TIME command.
            self.runtime.submit(
                CommandKind.ADVANCE_TIME,
                "runtime",
                {"duration_s": self.tick_simulation_s},
            )
            self.runtime.drain()
        except Exception:
            # Do not move clinical time again after a host/engine failure.  The
            # caller may inspect the state and explicitly resume only if safe.
            if self.runtime.state == RuntimeState.RUNNING:
                self.runtime.pause_by_system()
            raise
        elapsed = self.monotonic() - started
        remaining = self.tick_simulation_s - elapsed
        slept = 0.0
        if remaining > 0:
            self.sleep(remaining)
            slept = remaining
        self._tick_index += 1
        return TickResult(
            tick_index=self._tick_index,
            advanced_simulation_s=self.tick_simulation_s,
            wall_elapsed_s=elapsed,
            slept_s=slept,
            overrun_s=max(0.0, -remaining),
            state=self.runtime.state,
        )

    def run_ticks(self, count: int) -> tuple[TickResult, ...]:
        """Run a finite number of paced ticks for headless operation/testing."""
        if count < 0:
            raise ValueError("count must be non-negative")
        return tuple(self.tick_once() for _ in range(count))
