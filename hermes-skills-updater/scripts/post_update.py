"""Runs on this device after hermes-skills-updater is updated (by hermes-skills-updater) or after its new files
arrive through Hermes Device Sync. Must be safe to run more than once."""
import json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HH = Path(os.environ.get("HERMES_HOME") or (Path(os.environ["LOCALAPPDATA"]) / "hermes" if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".hermes"))


# stable copy for shell wrappers (e.g. Hermes Device Sync asks about updates before Hermes opens)
(HH / "scripts").mkdir(parents=True, exist_ok=True)
shutil.copy2(SKILL / "scripts" / "updater.py", HH / "scripts" / "hermes-skills-updater.py")
dst = HH / "plugins" / "skills-updater"
shutil.copytree(SKILL / "plugin" / "skills-updater", dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
print("skills-updater: updater and plugin refreshed")
