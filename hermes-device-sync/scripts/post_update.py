"""Runs on this device after hermes-device-sync is updated (by hermes-skills-updater) or after its new files
arrive through Hermes Device Sync. Must be safe to run more than once."""
import json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
HH = Path(os.environ.get("HERMES_HOME") or (Path(os.environ["LOCALAPPDATA"]) / "hermes" if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".hermes"))


cfg = json.loads((HH / "hermes-sync.json").read_text(encoding="utf-8")) if (HH / "hermes-sync.json").exists() else None
if cfg and cfg.get("repo") and cfg.get("device"):
    # Re-run the (idempotent) setup with the new package: it overwrites the scripts in the sync repo
    # (so every device gets them on its next sync), refreshes the shell wrapper and the hook.
    data = Path(cfg.get("data_dir") or Path(cfg["repo"]) / "hermes-sync")
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "setup.py"), "--repo", cfg["repo"],
                        "--device", cfg["device"], "--subdir", data.name, "--update-scripts"],
                       capture_output=True, text=True)
    print("\n".join(l for l in r.stdout.splitlines() if l.strip())[-1500:])
    sys.exit(r.returncode)
