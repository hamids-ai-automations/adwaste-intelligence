"""Headless render & workflow smoke check for AdWaste Intelligence.

Boots ``app.py`` via ``streamlit.testing.v1.AppTest`` on the landing state,
loads the 1,500-row demo account, verifies all 4 executive tabs render
without exceptions, and exercises negative staging + conflict guard.

Usage:
    python scripts/smoke_pages.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    if app.exception:
        print("[FAIL] landing render:", [e.value for e in app.exception])
        return 1
    print(f"[OK ] landing render ({len(app.button)} button(s))")

    demo_btn = next(
        (b for b in app.button if "demo" in b.label.lower()),
        None,
    )
    if demo_btn is None:
        print("[FAIL] Load Demo Account button not found on landing screen")
        return 1

    app = demo_btn.click().run()
    if app.exception:
        print("[FAIL] demo dashboard render:", [e.value for e in app.exception])
        return 1
    if len(app.tabs) != 4:
        print(f"[FAIL] expected 4 tabs, got {len(app.tabs)}")
        return 1
    print("[OK ] demo dashboard rendered all 4 tabs cleanly")

    stage_btn = next(
        (b for b in app.button if "add checked n-grams" in b.label.lower()),
        None,
    )
    if stage_btn is None:
        print("[FAIL] Tab 2 negative staging button missing")
        return 1

    app = stage_btn.click().run()
    if app.exception:
        print("[FAIL] Tab 2 -> Tab 4 staging & conflict guard:", [e.value for e in app.exception])
        return 1
    print(f"[OK ] staging & conflict guard rendered ({len(app.dataframe)} dataframe(s))")

    print("\nRESULT: ALL SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
