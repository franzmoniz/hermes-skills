"""Runs on this device after hermes-terminal is updated (hermes-skills-updater) or its new files arrive
through Hermes Device Sync. Safe to run more than once: re-runs the idempotent setup when installed."""
import os, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HH = Path(os.environ.get("HERMES_HOME") or (Path(os.environ["LOCALAPPDATA"]) / "hermes" if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".hermes"))
if (HH / "hermes-terminal.json").exists():
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "setup.py")], capture_output=True, text=True)
    print(r.stdout.strip()[-1200:])
    sys.exit(r.returncode)
