"""Root conftest — ensures the repository root is importable (``import src``)
when running plain ``pytest`` from the project root."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
