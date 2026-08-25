from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nexora_vpe.pulse_adapter import PulseAdapter, PulseAdapterConfig


class _FakeStream:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.flush_calls = 0
        self.readline_calls = 0
        self.closed = False

    def write(self, value: str) -> None:
        self.writes.append(value)

    def flush(self) -> None:
        self.flush_calls += 1

    def readline(self) -> str:
        self.readline_calls += 1
        raise AssertionError("close() must not read stdout when select reported no readiness")

    def read(self) -> str:
        return ""

    def close(self) -> None:
        self.closed = True


class _UnresponsiveProcess:
    def __init__(self) -> None:
        self.stdin = _FakeStream()
        self.stdout = _FakeStream()
        self.stderr = _FakeStream()
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_timeouts: list[float] = []

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1

    def wait(self, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        if len(self.wait_timeouts) == 1:
            raise subprocess.TimeoutExpired("fake-pulse", timeout)
        return 0


class PulseAdapterShutdownTest(unittest.TestCase):
    def test_close_does_not_block_on_quit_response_and_falls_back_to_bounded_kill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            initial_state = base / "initial.json"
            initial_state.write_text("{}", encoding="utf-8")
            adapter = PulseAdapter(
                PulseAdapterConfig(
                    server_executable=Path(sys.executable),
                    pulse_working_directory=base,
                    initial_state_file=initial_state,
                    request_timeout_s=0.01,
                )
            )
            process = _UnresponsiveProcess()
            adapter._process = process  # type: ignore[assignment]  # Fake subprocess boundary.

            with patch("nexora_vpe.pulse_adapter.select.select", return_value=([], [], [])) as mocked_select:
                adapter.close()

        self.assertEqual(["QUIT\n"], process.stdin.writes)
        self.assertEqual(1, process.stdin.flush_calls)
        self.assertEqual(0, process.stdout.readline_calls)
        mocked_select.assert_called_once_with([process.stdout], [], [], 0.01)
        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(1, process.kill_calls)
        self.assertEqual([PulseAdapter._SHUTDOWN_TIMEOUT_S, PulseAdapter._SHUTDOWN_TIMEOUT_S], process.wait_timeouts)
        self.assertTrue(process.stdin.closed)
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)


if __name__ == "__main__":
    unittest.main()
