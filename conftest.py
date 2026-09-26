"""Put the repository root on sys.path so tests can import ``battery.*``.

pytest inserts the directory containing each test module rather than the
repository root, and ``tests/`` holds no package marker, so the suite fails
with ModuleNotFoundError at collection without this hook. It also keeps
``python3 -m unittest discover -s tests`` and direct script runs working.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
