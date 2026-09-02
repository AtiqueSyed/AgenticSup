"""`scripts/check_complexity.py` must pass against `src` -- run as a subprocess so
this test exercises exactly what CI would run, with no import-path trickery."""

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_ROOT / "scripts" / "check_complexity.py"


def test_check_complexity_passes_for_src():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "src"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "OK" in result.stdout
