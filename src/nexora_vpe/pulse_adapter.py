"""Production Pulse adapter backed by one long-lived Pulse SDK process.

The adapter preserves the narrow :class:`PhysiologyAdapter` contract. It is
engineering infrastructure for a formative simulation only; it does not offer
medical advice, diagnosis, or high-stakes assessment.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import math
import os
import select
import subprocess
import tempfile
from typing import Any, Mapping, Sequence

from .adapter import PhysiologyAdapter
from .scenario import S0Scenario


class PulseAdapterError(RuntimeError):
    """Raised when the pinned Pulse adapter process cannot satisfy its contract."""


@dataclass(frozen=True)
class PulseAdapterConfig:
    """Local paths and process limits required by the production adapter."""

    server_executable: Path
    pulse_working_directory: Path
    initial_state_file: Path
    state_directory: Path | None = None
    request_timeout_s: float = 30.0

    def validate(self) -> None:
        if not self.server_executable.is_file() or not os.access(self.server_executable, os.X_OK):
            raise PulseAdapterError(f"Pulse adapter server is not executable: {self.server_executable}")
        if not self.pulse_working_directory.is_dir():
            raise PulseAdapterError(f"Pulse working directory does not exist: {self.pulse_working_directory}")
        if not self.initial_state_file.is_file():
            raise PulseAdapterError(f"Pulse initial state is missing: {self.initial_state_file}")
        if not math.isfinite(self.request_timeout_s) or self.request_timeout_s <= 0:
            raise PulseAdapterError("Pulse request timeout must be positive and finite")


class PulseAdapter(PhysiologyAdapter):
    """Own one local Pulse SDK server process for one S0 scenario run.

    The C++ server exposes only the S0 actions already validated by the runtime:
    existing internal splenic hemorrhage, constrained Saline/PackedRBC infusion,
    time advancement, telemetry, and local state save/restore. The client never
    transmits raw Pulse actions supplied by a learner, UI, or language model.
    """

    _ADAPTER_VERSION = "pulse-process-adapter/1.0"

    def __init__(self, config: PulseAdapterConfig) -> None:
        config.validate()
        self._config = config
        self._process: subprocess.Popen[str] | None = None
        self._engine_version = ""
        self._pulse_hash = ""
        self._simulation_time_s = 0.0
        self._scenario_id = ""
        self._state_sequence = 0
        self._temporary_state_directory: tempfile.TemporaryDirectory[str] | None = None
        self._state_directory: Path | None = None
        self._bootstrapped = False

    @property
    def engine_version(self) -> str:
        self._require_bootstrapped()
        return self._engine_version

    @property
    def simulation_time_s(self) -> float:
        self._require_bootstrapped()
        self._simulation_time_s = self._parse_time(self._request(("TIME",))[0])
        return self._simulation_time_s

    def bootstrap(self, scenario: S0Scenario) -> None:
        scenario.validate()
        if self._bootstrapped:
            raise PulseAdapterError("PulseAdapter is already bootstrapped")
        self._start_process()
        version_fields = self._request(("VERSION",))
        if len(version_fields) != 2:
            self.close()
            raise PulseAdapterError("Pulse adapter returned an invalid VERSION response")
        pulse_version, pulse_hash = version_fields
        if not scenario.pulse_revision.startswith(pulse_hash):
            self.close()
            raise PulseAdapterError(
                "Pulse SDK hash does not match the scenario pin: "
                f"expected prefix {scenario.pulse_revision[:7]}, received {pulse_hash}"
            )
        state_file = self._config.initial_state_file.resolve()
        bootstrap_fields = self._request(
            (
                "BOOTSTRAP",
                str(state_file),
                scenario.hemorrhage_compartment,
                self._format_positive(scenario.hemorrhage_flow_rate_ml_min, "hemorrhage flow"),
            )
        )
        if len(bootstrap_fields) != 1:
            self.close()
            raise PulseAdapterError("Pulse adapter returned an invalid BOOTSTRAP response")
        self._engine_version = f"pulse/{pulse_version}+{pulse_hash}"
        self._pulse_hash = pulse_hash
        self._simulation_time_s = self._parse_time(bootstrap_fields[0])
        self._scenario_id = scenario.scenario_id
        self._state_directory = self._prepare_state_directory()
        self._bootstrapped = True

    def advance(self, duration_s: float) -> None:
        self._require_bootstrapped()
        response = self._request(("ADVANCE", self._format_positive(duration_s, "duration")))
        if len(response) != 1:
            raise PulseAdapterError("Pulse adapter returned an invalid ADVANCE response")
        new_time_s = self._parse_time(response[0])
        if new_time_s <= self._simulation_time_s:
            raise PulseAdapterError("Pulse time did not increase after an accepted advance request")
        self._simulation_time_s = new_time_s

    def apply_intervention(self, payload: Mapping[str, Any]) -> None:
        self._require_bootstrapped()
        compound = payload.get("compound")
        volume_ml = payload.get("volume_ml")
        rate_ml_min = payload.get("rate_ml_min")
        if compound not in {"Saline", "PackedRBC"}:
            raise ValueError("PulseAdapter only accepts S0 constrained compounds")
        response = self._request(
            (
                "APPLY",
                str(compound),
                self._format_positive(volume_ml, "intervention volume"),
                self._format_positive(rate_ml_min, "intervention rate"),
            )
        )
        if len(response) != 1:
            raise PulseAdapterError("Pulse adapter returned an invalid APPLY response")
        returned_time_s = self._parse_time(response[0])
        if not math.isclose(returned_time_s, self._simulation_time_s, abs_tol=1e-6):
            raise PulseAdapterError("Pulse time changed while applying an intervention")

    def telemetry(self, requested_keys: tuple[str, ...]) -> Mapping[str, float]:
        self._require_bootstrapped()
        if not requested_keys:
            raise ValueError("At least one telemetry key is required")
        if len(set(requested_keys)) != len(requested_keys):
            raise ValueError("Telemetry keys must be unique")
        response = self._request(("TELEMETRY", *requested_keys))
        if len(response) != len(requested_keys) + 1:
            raise PulseAdapterError("Pulse adapter returned an unexpected telemetry field count")
        returned_time_s = self._parse_time(response[0])
        values: dict[str, float] = {}
        for field in response[1:]:
            key, separator, raw_value = field.partition("=")
            if not separator or key not in requested_keys or key in values:
                raise PulseAdapterError("Pulse adapter returned malformed telemetry")
            values[key] = self._parse_finite(raw_value, f"telemetry {key}")
        if set(values) != set(requested_keys):
            raise PulseAdapterError("Pulse adapter telemetry keys do not match request")
        if returned_time_s + 1e-6 < self._simulation_time_s:
            raise PulseAdapterError("Pulse telemetry reported time moving backward outside restore")
        self._simulation_time_s = returned_time_s
        return {key: values[key] for key in requested_keys}

    def save_state(self) -> Mapping[str, Any]:
        self._require_bootstrapped()
        assert self._state_directory is not None
        self._state_sequence += 1
        path = self._state_directory / f"pulse-state-{self._state_sequence:06d}.json"
        response = self._request(("SAVE", str(path)))
        if len(response) != 1 or not path.is_file():
            raise PulseAdapterError("Pulse adapter did not produce a requested state file")
        returned_time_s = self._parse_time(response[0])
        if not math.isclose(returned_time_s, self._simulation_time_s, abs_tol=1e-6):
            raise PulseAdapterError("Pulse time changed while saving a state")
        return {
            "adapter_type": self._ADAPTER_VERSION,
            "engine_version": self.engine_version,
            "pulse_hash": self._pulse_hash,
            "scenario_id": self._scenario_id,
            "simulation_time_s": self._simulation_time_s,
            "state_path": str(path),
            "state_sha256": self._sha256(path),
        }

    def restore_state(self, state: Mapping[str, Any]) -> None:
        self._require_bootstrapped()
        if state.get("adapter_type") != self._ADAPTER_VERSION:
            raise ValueError("Snapshot belongs to a different adapter type")
        if state.get("engine_version") != self.engine_version or state.get("pulse_hash") != self._pulse_hash:
            raise ValueError("Snapshot belongs to a different Pulse engine revision")
        if state.get("scenario_id") != self._scenario_id:
            raise ValueError("Snapshot belongs to a different scenario")
        path = Path(str(state.get("state_path", ""))).resolve()
        assert self._state_directory is not None
        if self._state_directory.resolve() not in path.parents or not path.is_file():
            raise ValueError("Snapshot state file is unavailable or outside the adapter state directory")
        if state.get("state_sha256") != self._sha256(path):
            raise ValueError("Snapshot state file digest does not match recorded state")
        response = self._request(("RESTORE", str(path)))
        if len(response) != 1:
            raise PulseAdapterError("Pulse adapter returned an invalid RESTORE response")
        restored_time_s = self._parse_time(response[0])
        expected_time_s = self._parse_finite(str(state.get("simulation_time_s")), "snapshot time")
        if not math.isclose(restored_time_s, expected_time_s, abs_tol=1e-6):
            raise PulseAdapterError("Pulse restored a state at an unexpected simulation time")
        self._simulation_time_s = restored_time_s

    def close(self) -> None:
        process = self._process
        self._process = None
        self._bootstrapped = False
        if process is not None:
            try:
                if process.poll() is None and process.stdin is not None:
                    process.stdin.write("QUIT\n")
                    process.stdin.flush()
                    select.select([process.stdout], [], [], min(2.0, self._config.request_timeout_s))
                    if process.stdout is not None:
                        process.stdout.readline()
            except (BrokenPipeError, OSError):
                pass
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2.0)
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass
        if self._temporary_state_directory is not None:
            self._temporary_state_directory.cleanup()
            self._temporary_state_directory = None
        self._state_directory = None

    def __enter__(self) -> "PulseAdapter":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _start_process(self) -> None:
        if self._process is not None:
            raise PulseAdapterError("Pulse adapter process already exists")
        self._process = subprocess.Popen(
            [str(self._config.server_executable.resolve())],
            cwd=self._config.pulse_working_directory.resolve(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def _request(self, fields: Sequence[str]) -> list[str]:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise PulseAdapterError("Pulse adapter process is not running")
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise PulseAdapterError(f"Pulse adapter exited unexpectedly: {stderr.strip()}")
        if any("\t" in field or "\n" in field or "\r" in field for field in fields):
            raise PulseAdapterError("Pulse adapter protocol fields cannot contain tabs or newlines")
        try:
            process.stdin.write("\t".join(fields) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PulseAdapterError("Pulse adapter process is unavailable") from exc
        ready, _, _ = select.select([process.stdout], [], [], self._config.request_timeout_s)
        if not ready:
            self.close()
            raise PulseAdapterError("Pulse adapter command timed out")
        response = process.stdout.readline().rstrip("\n\r")
        if not response:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise PulseAdapterError(f"Pulse adapter produced no response: {stderr.strip()}")
        response_fields = response.split("\t")
        if response_fields[0] == "OK":
            return response_fields[1:]
        if response_fields[0] == "ERR":
            detail = response_fields[1] if len(response_fields) > 1 else "unknown server error"
            raise PulseAdapterError(f"Pulse adapter rejected command: {detail}")
        raise PulseAdapterError("Pulse adapter returned an invalid protocol status")

    def _prepare_state_directory(self) -> Path:
        if self._config.state_directory is not None:
            directory = self._config.state_directory.resolve()
            directory.mkdir(parents=True, exist_ok=True)
            return directory
        self._temporary_state_directory = tempfile.TemporaryDirectory(prefix="nexora-pulse-adapter-")
        return Path(self._temporary_state_directory.name).resolve()

    def _require_bootstrapped(self) -> None:
        if not self._bootstrapped:
            raise PulseAdapterError("PulseAdapter must be bootstrapped before use")

    @staticmethod
    def _format_positive(value: Any, name: str) -> str:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError(f"{name} must be a positive finite number")
        return format(float(value), ".17g")

    @staticmethod
    def _parse_finite(raw: str, name: str) -> float:
        try:
            value = float(raw)
        except ValueError as exc:
            raise PulseAdapterError(f"Pulse adapter returned non-numeric {name}") from exc
        if not math.isfinite(value):
            raise PulseAdapterError(f"Pulse adapter returned non-finite {name}")
        return value

    @classmethod
    def _parse_time(cls, raw: str) -> float:
        value = cls._parse_finite(raw, "simulation time")
        if value < 0:
            raise PulseAdapterError("Pulse adapter returned a negative simulation time")
        return value

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as state_file:
            for chunk in iter(lambda: state_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
