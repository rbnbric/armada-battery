"""Build the credential-free GitHub Pages demonstration.

The browser uses the same synthetic API fixture as the local UI journey tests.
No IRIS endpoint or model is contacted by this page.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build(out: Path) -> None:
    static = out / "static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("app.js", "app.css", "battery-logo.png"):
        shutil.copy2(ROOT / "static" / name, static / name)
    shutil.copy2(ROOT / "tests/fixtures/demo-api.js", static / "demo-api.js")
    cases = json.loads((ROOT / "tests/fixtures/ux_cases.json").read_text())
    fixture = (ROOT / "tests/fixtures/ux-network.js").read_text()
    assert "const fixtureCases = CASES;" in fixture
    fixture = fixture.replace("const fixtureCases = CASES;", "const fixtureCases = " + json.dumps(cases) + ";", 1)
    (static / "ux-api.js").write_text(fixture)

    html = (ROOT / "static/index.html").read_text()
    html = html.replace('href="/static/', 'href="./static/').replace('src="/static/', 'src="./static/')
    app_tag = '<script src="./static/app.js?'
    assert app_tag in html
    html = html.replace(app_tag, '<script src="./static/demo-api.js"></script>\n    <script src="./static/ux-api.js"></script>\n    ' + app_tag, 1)
    (out / "index.html").write_text(html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.out)
