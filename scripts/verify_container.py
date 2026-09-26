"""Verify that the composed Battery service is reading from IRIS."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


base_url = os.environ.get("BATTERY_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
deadline = time.monotonic() + 180
last_error = "service did not respond"

while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(f"{base_url}/api/state", timeout=5) as response:
            payload = json.load(response)
        if payload.get("mode") != "iris":
            raise RuntimeError(f"expected iris mode, received {payload.get('mode')!r}")
        server = payload.get("server", {})
        tasks = payload.get("tasks", [])
        with urllib.request.urlopen(
            f"{base_url}/api/observations", timeout=15
        ) as response:
            observations = json.load(response).get("areas", {})
        # A connection-only check previously missed a broken task definition adapter.
        if tasks:
            task_id = tasks[0]["Id"]
            request = urllib.request.Request(
                f"{base_url}/api/intents/task/{task_id}/run",
                data=json.dumps({"task_definition_reviewed": False}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                preparation = json.load(response)
            if preparation.get("certificate"):
                raise RuntimeError(
                    "Unreviewed task unexpectedly received authorization"
                )
            if not preparation.get("task", {}).get("Name"):
                raise RuntimeError("Task preparation did not resolve the definition")
        print(
            json.dumps(
                {
                    "ok": True,
                    "task_preflight": "blocked as unreviewed"
                    if tasks
                    else "not exercised: no tasks",
                    "qualification": "read and blocked-preflight smoke; no live mutation proof",
                    "mode": payload["mode"],
                    "server_version": server.get("version"),
                    "authenticated_user": server.get("username"),
                    "task_count": len(tasks),
                    "observation_quality": {
                        name: area.get("quality") for name, area in observations.items()
                    },
                    "changes_enabled": payload.get("changes_enabled"),
                },
                indent=2,
            )
        )
        sys.exit(0)
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        last_error = str(exc)
        time.sleep(3)

print(f"container verification failed: {last_error}", file=sys.stderr)
sys.exit(1)
