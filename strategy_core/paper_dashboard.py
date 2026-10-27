"""Loopback-only, read-only dashboard for a standalone Tool Rack PAPER run.

The engine publishes detached bytes; HTTP threads cannot access mutable engine
objects, read run files, or send commands. No third-party browser resources.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any, Mapping
from urllib.parse import urlsplit

from strategy_core.nautilus_projection import NautilusProjection


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


class _LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Dashboard:
    """`start() -> URL`, `publish(status, geometry_rows)`, `close()`."""

    def __init__(self, run_dir: str | Path, port: int = 0):
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("DASHBOARD_PORT_INVALID")
        self.run_dir = Path(run_dir)
        self.port = port
        self._lock = threading.Lock()
        self._version = 0
        self._payload = json.dumps({"version": 0, "status": None, "geometry_rows": []}).encode()
        self._projection = NautilusProjection()
        self._nautilus_payload = b"null"
        self._server = None
        self._thread = None
        self._closed = False
        directory = Path(__file__).with_name("nautilus")
        self._assets = {
            "/": ("text/html; charset=utf-8", (directory / "index.html").read_bytes()),
        }
        for filename in ("style.css", "bridge.css", "chart.js", "reliability-ui.js", "app.js", "bridge.js"):
            content_type = "text/css; charset=utf-8" if filename.endswith(".css") else "application/javascript; charset=utf-8"
            self._assets["/nautilus/" + filename] = (content_type, (directory / filename).read_bytes())

    def observe(self, status: Mapping[str, Any]) -> None:
        """Capture every engine beat before the slower browser publication.

        Called only by the engine owner. The projection stores detached,
        bounded display records; the HTTP thread only reads published bytes.
        """
        if not self._closed:
            self._projection.observe(status)

    def publish(self, status: Mapping[str, Any], geometry_rows: tuple | list,
                chart_data: Mapping[str, Any] | None = None) -> None:
        if self._closed:
            return
        # Bound the chart independently of the engine's physical history.
        rows = [{key: row.get(key) for key in ("epoch_ms", "btc_price", "ema9", "ema30")}
                for row in list(geometry_rows)[-10000:]]
        with self._lock:
            version = self._version + 1
        payload = json.dumps({"version": version, "status": _plain(status),
                              "geometry_rows": _plain(rows)},
                             ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
        projected = self._projection.project(status, geometry_rows, chart_data=chart_data)
        nautilus_payload = json.dumps(projected, ensure_ascii=True, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")
        with self._lock:
            self._payload = payload
            self._nautilus_payload = nautilus_payload
            self._version = version

    def start(self) -> str:
        if self._closed or self._server is not None:
            raise RuntimeError("DASHBOARD_ALREADY_STARTED_OR_CLOSED")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _respond(self, code, content_type, body, *, head=False):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
                self.end_headers()
                if not head:
                    try:
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

            def _read(self, head=False):
                # Reject nonloopback Host names as well as binding only IPv4
                # loopback. No CORS header is supplied to other origins.
                host = self.headers.get("Host", "").split(":", 1)[0].lower()
                if host not in ("127.0.0.1", "localhost"):
                    return self._respond(403, "text/plain", b"Loopback host required", head=head)
                path = urlsplit(self.path).path
                if path == "/api/state":
                    with owner._lock:
                        payload = owner._payload
                    return self._respond(200, "application/json; charset=utf-8", payload, head=head)
                if path == "/api/nautilus":
                    with owner._lock:
                        payload = owner._nautilus_payload
                    return self._respond(200, "application/json; charset=utf-8", payload, head=head)
                asset = owner._assets.get(path)
                if asset is None:
                    return self._respond(404, "text/plain", b"Not found", head=head)
                return self._respond(200, asset[0], asset[1], head=head)

            def do_GET(self):
                self._read()

            def do_HEAD(self):
                self._read(head=True)

            def _readonly(self):
                self.close_connection = True
                self._respond(405, "text/plain", b"Read-only dashboard")

            do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _readonly

        # Match the familiar Nautilus origin so saved display preferences can
        # survive sessions. Explicit port 0 still requests an ephemeral port.
        ports = range(8580, 8590) if self.port == 8580 else (self.port,)
        for port in ports:
            try:
                self._server = _LocalServer(("127.0.0.1", port), Handler)
                break
            except OSError as exc:
                if exc.errno not in (errno.EADDRINUSE, 10048) or port == ports[-1]:
                    raise
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": .1}, daemon=True,
                                        name="ToolRack-ReadOnly-Dashboard")
        self._thread.start()
        return f"http://127.0.0.1:{self.port}/"

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)
