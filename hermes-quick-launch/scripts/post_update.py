"""Runs on this device after hermes-quick-launch is updated (by hermes-skills-updater) or after its new files
arrive through Hermes Device Sync. Must be safe to run more than once."""
import json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HH = Path(os.environ.get("HERMES_HOME") or (Path(os.environ["LOCALAPPDATA"]) / "hermes" if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".hermes"))


if os.name == "nt" and (HH / "hermes-launch.vbs").exists():  # installed before: re-run the safe installer
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(SKILL / "scripts" / "install.ps1")], capture_output=True, text=True)
    print(r.stdout.strip())
    sys.exit(r.returncode)
