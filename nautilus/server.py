"""The Nautilus: loopback-only, read-only desktop dashboard for Tachys PAPER.

Launch independently. This process cannot start, stop, import or trade with Tachys.
No pip/npm installation, remote assets, telemetry uploads, or disk cache required.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
from adapter import Adapter, VERSION as ADAPTER_VERSION, resolve_run

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "application/javascript; charset=utf-8"),
          "/chart.js": ("chart.js", "application/javascript; charset=utf-8"),
          "/bridge.js": ("bridge.js", "application/javascript; charset=utf-8"),
          "/bridge.css": ("bridge.css", "text/css; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


def finite_json(obj, depth=0):
    if depth > 20:
        return None
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): finite_json(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [finite_json(v, depth + 1) for v in obj]
    return obj


class Publisher:
    def __init__(self, adapter):
        self.adapter = adapter
        self.body = b'{}'
        self.compressed = b''
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.last_error = None
        self.last_good = None

    def once(self):
        try:
            state = finite_json(self.adapter.poll())
            state["adapter_version"] = ADAPTER_VERSION
            state["version"] = VERSION
            self.last_good = state
            self.last_error = None
        except Exception as exc:
            # Never keep an old snapshot looking live when an optional reader fails.
            self.last_error = f"{type(exc).__name__}: {exc}"
            state = {"error": self.last_error, "version": VERSION, "server_now": time.time()}
        body = json.dumps(state, separators=(",", ":"), allow_nan=False).encode("utf-8")
        compressed = gzip.compress(body, compresslevel=2)
        with self.lock:
            self.body, self.compressed = body, compressed

    def loop(self):
        while not self.stop.is_set():
            start = time.monotonic()
            self.once()
            self.stop.wait(max(.1, 1 - (time.monotonic() - start)))


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    server_version = "Nautilus/" + VERSION
    sys_version = ""

    def log_message(self, fmt, *args):
        pass  # Do not generate another large disk log just to read the engine log.

    def allowed(self):
        host = self.headers.get("Host", "")
        valid_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        if host not in valid_hosts:
            return False
        if origin and origin not in {"http://" + x for x in valid_hosts}:
            return False
        return self.headers.get("Sec-Fetch-Site", "") != "cross-site"

    def send(self, code, body, content_type="application/json; charset=utf-8", compressed=False):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if compressed:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        if not self.allowed():
            self.send(403, b'{"error":"Local same-origin access only"}')
            return
        path = urlsplit(self.path).path
        if path == "/health":
            self.send(200, json.dumps({"app": "The Nautilus", "version": VERSION, "readonly": True}).encode())
        elif path == "/api/state":
            if not secrets.compare_digest(self.headers.get("X-Nautilus-Read", ""), self.server.token):
                self.send(403, b'{"error":"Missing local read token"}')
                return
            compressed = "gzip" in self.headers.get("Accept-Encoding", "")
            with self.server.publisher.lock:
                body = self.server.publisher.compressed if compressed else self.server.publisher.body
            self.send(200, body, compressed=compressed)
        elif path in ASSETS:
            name, mime = ASSETS[path]
            try:
                body = (ROOT / "static" / name).read_bytes()
                if name == "index.html":
                    body = body.replace(b"__NAUTILUS_TOKEN__", self.server.token.encode())
                self.send(200, body, mime)
            except OSError:
                self.send(500, b'{"error":"Nautilus installation is incomplete"}')
        else:
            self.send(404, b'{"error":"Not found"}')

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        self.send(405, b'{"error":"Read-only dashboard; no write or trading endpoints"}')

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST


def main(argv=None):
    p = argparse.ArgumentParser(description="The Nautilus — read-only PAPER bridge")
    p.add_argument("--lab", type=Path, default=Path(r"C:\KalshiBTCBot_666Lab"))
    p.add_argument("--build", default="R6", help="Exact live build pointer; default R6")
    p.add_argument("--run", type=Path, help="Explicit run directory; never chosen by latest mtime")
    p.add_argument("--review", action="store_true", help="Read a relocated archive; no live marks or running timer")
    p.add_argument("--port", type=int, default=8580)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--check", action="store_true", help="Validate sources once; no browser/server/engine launch")
    args = p.parse_args(argv)
    if args.review and not args.run:
        p.error("--review requires --run pointing at an extracted recorded run")
    if not 1024 <= args.port <= 65525:
        p.error("--port must be between 1024 and 65525")
    try:
        run, manifest, pointer = resolve_run(args.lab.resolve(), args.build.upper(), args.run, args.review)
        adapter = Adapter(run, manifest, args.lab.resolve(), pointer, args.review)
        pub = Publisher(adapter)
        pub.once()
        if pub.last_error:
            raise ValueError(pub.last_error)
        if args.check:
            d = pub.last_good
            print(json.dumps({"nautilus": VERSION, "run": d["run"], "accounting": d["accounting"],
                              "candles": len(d["candles"]), "diagnostics": d["diagnostics"]}, indent=2))
            return 0 if not d["accounting"]["issues"] else 2
        server = None
        for port in range(args.port, args.port + 10):
            try:
                server = LocalServer(("127.0.0.1", port), Handler)
                break
            except OSError:
                continue
        if server is None:
            raise ValueError("No free Nautilus port. No existing process was touched.")
        server.token, server.publisher = secrets.token_urlsafe(32), pub
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"\nTHE NAUTILUS {VERSION} | PAPER | READ ONLY\nBuild: {manifest['version']}\nRun: {run}\nOpen: {url}\nClosing Nautilus does not stop Tachys. Ctrl+C closes only this viewer.\n", flush=True)
        thread = threading.Thread(target=pub.loop, name="NautilusTelemetryReader", daemon=True)
        thread.start()
        if not args.no_browser:
            threading.Timer(.6, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever(poll_interval=.4)
        except KeyboardInterrupt:
            print("\nNautilus closed. Trading engine unchanged.")
        finally:
            pub.stop.set()
            server.server_close()
            thread.join(timeout=3)
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"NAUTILUS DID NOT ATTACH: {exc}\nNo engine or existing cockpit was changed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
