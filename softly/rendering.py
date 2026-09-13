"""runs generated animation scripts through the subprocess renderer."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import ROOT

RENDER_TIMEOUT = 240  # seconds; a runaway script gets killed, not debugged

# the subprocess executes model-written code — hand it a minimal environment
# so credentials (ANTHROPIC_API_KEY etc.) are never inherited.
_ENV_KEEP = ("PATH", "HOME", "TMPDIR", "PYTHONPATH", "LANG", "LC_ALL")


def _minimal_env() -> dict[str, str]:
    return {key: os.environ[key] for key in _ENV_KEEP if key in os.environ}


def render(script_path: Path, out_path: Path, sound_path: Path | None = None) -> tuple[bool, str]:
    """returns (ok, log). blocking — call via asyncio.to_thread from async code."""
    cmd = [sys.executable, "-m", "softly.render_cli", str(script_path), str(out_path)]
    if sound_path is not None:
        cmd.append(str(sound_path))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT,
            cwd=str(ROOT),
            env=_minimal_env(),
        )
    except subprocess.TimeoutExpired:
        out_path.unlink(missing_ok=True)
        return False, f"render timed out after {RENDER_TIMEOUT}s"
    log = (proc.stdout + "\n" + proc.stderr).strip()
    ok = proc.returncode == 0 and out_path.exists()
    if not ok:
        out_path.unlink(missing_ok=True)
    return ok, log[-10000:]
