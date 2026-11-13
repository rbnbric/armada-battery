"""Loopback HTTP fixture in a separate process from the IRIS test caller."""

import http.server
import json
from pathlib import Path
import sys

directory = Path(sys.argv[1])


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        state = json.loads((directory / "state.json").read_text())
        counts = directory / "calls.txt"
        count = int(counts.read_text()) if counts.exists() else 0
        counts.write_text(str(count + 1))
        authorized = (
            self.headers.get("X-Battery-Adapter") == "battery-test-fixture-key-not-a-secret-20261113"
            and self.headers.get("X-Battery-Operator") == "fixture"
        )
        status = 200 if authorized else 403
        if state["mode"] == "denied":
            status = 401
        payload = ("x" * 65537 if state["mode"] == "oversize" else state["body"]).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 8080), Handler)
(directory / "ready").write_text("ready")
server.serve_forever()
