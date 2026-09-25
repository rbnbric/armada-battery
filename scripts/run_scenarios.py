"""Run Battery's deterministic contest demonstration."""

from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battery.scenarios import run_scenarios  # noqa: E402


report = run_scenarios()
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] == report["total"] else 1)
