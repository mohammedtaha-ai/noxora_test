from __future__ import annotations

import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from nexora_vpe import DeterministicPhysiologyAdapter, VpeClientFacade, VpeRuntime
from nexora_vpe.local_transport import LocalFacadeHttpServer
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class CountingAdapter(DeterministicPhysiologyAdapter):
    """Counts mutable physiology adapter entry points for client-read regressions."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def bootstrap(self, scenario: object) -> None:
        self.calls.append("bootstrap")
        super().bootstrap(scenario)  # type: ignore[arg-type]

    def advance(self, duration_s: float) -> None:
        self.calls.append("advance")
        super().advance(duration_s)

    def apply_intervention(self, payload: object) -> None:
        self.calls.append("apply_intervention")
        super().apply_intervention(payload)  # type: ignore[arg-type]

    def telemetry(self, requested_keys: tuple[str, ...]) -> dict[str, float]:
        self.calls.append("telemetry")
        return dict(super().telemetry(requested_keys))


class LocalFacadeHttpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = CountingAdapter()
        runtime = VpeRuntime(
            scenario=splenic_hemorrhage_learning_scenario(),
            adapter=self.adapter,
        )
        runtime.start()
        self.runtime = runtime
        self.facade = VpeClientFacade(runtime)
        self.server = LocalFacadeHttpServer(self.facade)
        self.server.start()
        self.addCleanup(self.server.stop)

    def _request(self, path: str, method: str = "GET", body: dict[str, object] | None = None, token: str | None = None) -> tuple[int, dict[str, object]]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.server.base_url + path,
            data=data,
            method=method,
            headers={
                "X-Nexora-Client-Token": self.server.client_token if token is None else token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=2.0) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_loopback_server_projects_manifest_and_snapshot_without_hidden_truth(self) -> None:
        status, manifest = self._request("/scenario")
        self.assertEqual(200, status)
        serialized = json.dumps(manifest, sort_keys=True)
        for forbidden in (
            "blood_volume",
            "total_hemorrhaged",
            "Spleen",
            "free_fluid_positive",
            "pulse_revision",
            "flow_rate",
            "pathology",
        ):
            self.assertNotIn(forbidden, serialized)

        status, snapshot = self._request("/snapshot")
        self.assertEqual(200, status)
        self.assertEqual(
            {"heart_rate_bpm", "mean_arterial_pressure_mmhg", "oxygen_saturation"},
            set(snapshot["telemetry"]),
        )
        self.assertNotIn("engine_version", snapshot)
        self.assertNotIn("reason", snapshot)

    def test_client_http_gets_do_not_touch_physiology_adapter(self) -> None:
        calls_before = tuple(self.adapter.calls)

        for path in ("/state", "/snapshot", "/events"):
            status, _ = self._request(path)
            self.assertEqual(200, status)

        self.assertEqual(calls_before, tuple(self.adapter.calls))

    def test_http_submits_command_but_host_processes_it(self) -> None:
        before = self.runtime.simulation_time_s
        status, accepted = self._request(
            "/commands",
            method="POST",
            body={
                "kind": "apply_intervention",
                "payload": {"intervention_id": "crystalloid_saline"},
                "request_id": "http-intervention-1",
            },
        )
        self.assertEqual(202, status)
        self.assertEqual("ACCEPTED", accepted["status"])
        self.assertEqual(before, self.runtime.simulation_time_s)
        self.assertEqual(1, len(self.runtime.queued_command_ids()))

        self.facade.process_pending()
        status, outcome = self._request("/commands/http-intervention-1")
        self.assertEqual(200, status)
        self.assertEqual("COMPLETED", outcome["status"])
        self.assertEqual("intervention.applied", outcome["events"][0]["event_type"])
        self.assertNotIn("compound", json.dumps(outcome, sort_keys=True))

    def test_transport_exposes_safe_structured_errors_and_no_clock_endpoint(self) -> None:
        status, unauthorized = self._request("/state", token="wrong-token")
        self.assertEqual(401, status)
        self.assertEqual("INVALID_COMMAND", unauthorized["error"]["code"])

        status, missing = self._request("/advance")
        self.assertEqual(404, status)
        serialized = json.dumps(missing, sort_keys=True)
        for forbidden in ("/home/", "Traceback", "Pulse", "adapter", "checkpoint"):
            self.assertNotIn(forbidden, serialized)

    def test_transport_refuses_non_loopback_binding(self) -> None:
        server = LocalFacadeHttpServer(self.facade, host="0.0.0.0")
        with self.assertRaisesRegex(ValueError, "loopback"):
            server.start()


if __name__ == "__main__":
    unittest.main()
