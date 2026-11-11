"""Runs on this device after hermes-model-return is updated (by hermes-skills-updater) or after its new files
arrive through Hermes Device Sync. Must be safe to run more than once."""
import json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HH = Path(os.environ.get("HERMES_HOME") or (Path(os.environ["LOCALAPPDATA"]) / "hermes" if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".hermes"))


dst = HH / "plugins" / "model-return"
if dst.exists():  # only refresh an installed plugin; never install it without the user's OK
    shutil.copytree(SKILL / "plugin" / "model-return", dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    print("model-return: plugin refreshed (restart Hermes to load the new version)")
