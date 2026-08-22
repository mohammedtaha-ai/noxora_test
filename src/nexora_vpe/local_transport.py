"""Minimal loopback HTTP/JSON transport for the learner-safe facade.

This module is a headless development spike.  It binds only to loopback, exposes
only client DTOs, and deliberately has no endpoint for simulation-clock control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

from .client_contracts import (
    ClientCommandStatus,
    ClientError,
    ClientErrorCode,
    CommandAccepted,
    CommandRequest,
)
from .client_facade import VpeClientFacade


@dataclass
class LocalFacadeHttpServer:
    """Serve a VpeClientFacade over loopback HTTP/JSON only.

    `process_pending` remains owned by the host loop.  The server may submit a
    client action but it can never advance simulation time or drain the queue.
    """

    facade: VpeClientFacade
    host: str = "127.0.0.1"
    port: int = 0
    client_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    _server: ThreadingHTTPServer | None = field(init=False, default=None)
    _thread: Thread | None = field(init=False, default=None)

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("Local transport has not been started")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def start(self) -> str:
        if self._server is not None:
            raise RuntimeError("Local transport is already running")
        if self.host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Local transport may bind only to loopback")
        server = ThreadingHTTPServer((self.host, self.port), self._handler_type())
        server.daemon_threads = True
        self._server = server
        self._thread = Thread(target=server.serve_forever, name="nexora-local-facade", daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server, self._thread = None, None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)

    def __enter__(self) -> "LocalFacadeHttpServer":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        facade = self.facade
        token = self.client_token

        class LocalFacadeRequestHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:
                # Avoid writing request details or accidental internal error text.
                return

            def do_GET(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                parsed = urlparse(self.path)
                path = parsed.path
                try:
                    if path == "/v1/scenario":
                        self._send_json(HTTPStatus.OK, facade.scenario_manifest().as_dict())
                        return
                    if path == "/v1/state":
                        self._send_json(HTTPStatus.OK, facade.current_state().as_dict())
                        return
                    if path == "/v1/snapshot":
                        snapshot = facade.current_snapshot()
                        if snapshot is None:
                            self._error(HTTPStatus.NOT_FOUND, ClientErrorCode.INVALID_STATE, "No learner-visible snapshot is available.")
                        else:
                            self._send_json(HTTPStatus.OK, snapshot.as_dict())
                        return
                    if path == "/v1/events":
                        after = parse_qs(parsed.query).get("after", [None])[0]
                        self._send_json(HTTPStatus.OK, {"events": [event.as_dict() for event in facade.new_events(after)]})
                        return
                    if path.startswith("/v1/commands/"):
                        request_id = path.removeprefix("/v1/commands/")
                        self._send_outcome(facade.query_command_outcome(request_id))
                        return
                    self._error(HTTPStatus.NOT_FOUND, ClientErrorCode.INVALID_COMMAND, "The requested client resource is not available.")
                except Exception:
                    self._error(HTTPStatus.INTERNAL_SERVER_ERROR, ClientErrorCode.INTERNAL_ERROR, "The client request could not be completed.")

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorized():
                    return
                if urlparse(self.path).path != "/v1/commands":
                    self._error(HTTPStatus.NOT_FOUND, ClientErrorCode.INVALID_COMMAND, "The requested client resource is not available.")
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                    if content_length <= 0 or content_length > 65536:
                        self._error(HTTPStatus.BAD_REQUEST, ClientErrorCode.INVALID_COMMAND, "The command body is invalid.")
                        return
                    raw = self.rfile.read(content_length)
                    body = json.loads(raw.decode("utf-8"))
                    if not isinstance(body, dict) or set(body) != {"kind", "payload", "request_id"}:
                        self._error(HTTPStatus.BAD_REQUEST, ClientErrorCode.INVALID_COMMAND, "The command body is invalid.")
                        return
                    result = facade.submit(
                        CommandRequest(
                            kind=body["kind"],
                            payload=body["payload"],
                            request_id=body["request_id"],
                        )
                    )
                    if isinstance(result, CommandAccepted):
                        self._send_json(HTTPStatus.ACCEPTED, result.as_dict())
                    else:
                        self._send_outcome(result)
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                    self._error(HTTPStatus.BAD_REQUEST, ClientErrorCode.INVALID_COMMAND, "The command body is invalid.")
                except Exception:
                    self._error(HTTPStatus.INTERNAL_SERVER_ERROR, ClientErrorCode.INTERNAL_ERROR, "The client request could not be completed.")

            def _authorized(self) -> bool:
                if not secrets.compare_digest(self.headers.get("X-Nexora-Client-Token", ""), token):
                    self._error(HTTPStatus.UNAUTHORIZED, ClientErrorCode.INVALID_COMMAND, "The client token is invalid.")
                    return False
                return True

            def _send_outcome(self, outcome: object) -> None:
                status = getattr(outcome, "status", None)
                if status == ClientCommandStatus.COMPLETED:
                    self._send_json(HTTPStatus.OK, outcome.as_dict())
                    return
                if status == ClientCommandStatus.PENDING:
                    self._send_json(HTTPStatus.ACCEPTED, outcome.as_dict())
                    return
                if status == ClientCommandStatus.AMBIGUOUS:
                    self._send_json(HTTPStatus.CONFLICT, outcome.as_dict())
                    return
                error = getattr(outcome, "error", None)
                code = getattr(error, "code", None)
                http_status = HTTPStatus.CONFLICT if code == ClientErrorCode.DUPLICATE_REQUEST_CONFLICT else HTTPStatus.BAD_REQUEST
                self._send_json(http_status, outcome.as_dict())

            def _error(self, status: HTTPStatus, code: ClientErrorCode, message: str) -> None:
                self._send_json(status, {"error": ClientError(code, message).as_dict()})

            def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
                self.send_response(status.value)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)

        return LocalFacadeRequestHandler
