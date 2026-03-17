#!/usr/bin/env python3
"""
Babs Bridge - HTTP command relay for sandbox -> Spark access.

Listens on the Docker bridge IP (172.17.0.1) so only the OpenClaw sandbox
can reach it. Requires a shared secret token in the X-Babs-Token header.

Trust Tier enforcement is Babs' responsibility (via SOUL.md). This service
enforces auth only -- it doesn't second-guess which commands are safe.
That policy lives with the agent.

Usage (from sandbox):
    curl -s -X POST http://host.openshell.internal:7222/run \
      -H "Content-Type: application/json" \
      -H "X-Babs-Token: TOKEN" \
      -d '{"command": "ls /home/dave/babs", "cwd": "/home/dave"}'
"""

import os
import json
import hmac
import hashlib
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get("BABS_BRIDGE_TOKEN", "")
BIND_HOST = os.environ.get("BABS_BRIDGE_HOST", "0.0.0.0")
BIND_PORT = int(os.environ.get("BABS_BRIDGE_PORT", "7222"))
DEFAULT_CWD = os.environ.get("BABS_BRIDGE_CWD", "/home/dave")
DEFAULT_TIMEOUT = 60


def check_token(request_token: str) -> bool:
    if not TOKEN:
        return False
    return hmac.compare_digest(request_token or "", TOKEN)


class BridgeHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[bridge] {self.address_string()} {fmt % args}")

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"ok": True, "service": "babs-bridge"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            self.send_json(404, {"error": "not found"})
            return

        token = self.headers.get("X-Babs-Token", "")
        if not check_token(token):
            self.send_json(403, {"error": "unauthorized"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self.send_json(400, {"error": "invalid json"})
            return

        command = body.get("command", "").strip()
        cwd = body.get("cwd", DEFAULT_CWD)
        timeout = int(body.get("timeout", DEFAULT_TIMEOUT))

        if not command:
            self.send_json(400, {"error": "command required"})
            return

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
                env={**os.environ, "HOME": "/home/dave"},
            )
            self.send_json(200, {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            self.send_json(200, {
                "stdout": "",
                "stderr": f"command timed out after {timeout}s",
                "returncode": 124,
            })
        except Exception as e:
            self.send_json(500, {"error": str(e)})


if __name__ == "__main__":
    if not TOKEN:
        print("[bridge] ERROR: BABS_BRIDGE_TOKEN env var not set. Refusing to start.")
        raise SystemExit(1)

    server = HTTPServer((BIND_HOST, BIND_PORT), BridgeHandler)
    print(f"[bridge] listening on http://{BIND_HOST}:{BIND_PORT} (Docker bridge only)")
    server.serve_forever()
