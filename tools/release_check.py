"""Release check for Hermes's Skills (also runs on GitHub for every push).

Every skill folder (a folder with SKILL.md) must have:
  - VERSION (x.y.z), the same as `version:` in SKILL.md (when present) and as skills.json;
  - CHANGELOG.md with a "## x.y.z" section for that version (Added / Changed / Fixed / Removed);
  - an `author:` mentioning franzmoniz (the updater only touches skills with it).
  python tools/release_check.py          check
  python tools/release_check.py --fix    rewrite skills.json from the VERSION files
Releasing a change to a skill: bump VERSION (and SKILL.md version), add the CHANGELOG section,
run this with --fix, commit. Users are then asked about the update when their Hermes starts.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors, reg = [], {}
for d in sorted(p.parent for p in ROOT.glob("*/SKILL.md")):
    n = d.name
    v = (d / "VERSION").read_text(encoding="utf-8").strip() if (d / "VERSION").exists() else None
    if not v or not re.fullmatch(r"\d+\.\d+\.\d+", v):
        errors.append(f"{n}: VERSION missing or not x.y.z")
        continue
    reg[n] = {"version": v}
    md = (d / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*([\d.]+)", md, re.M)
    if m and m.group(1) != v:
        errors.append(f"{n}: SKILL.md version {m.group(1)} != VERSION {v}")
    if not re.search(r"^author:.*franzmoniz", md, re.M | re.I):
        errors.append(f"{n}: SKILL.md author must mention franzmoniz")
    cl = d / "CHANGELOG.md"
    if not cl.exists() or not re.search(rf"^##\s+\[?v?{re.escape(v)}\b", cl.read_text(encoding="utf-8"), re.M):
        errors.append(f"{n}: CHANGELOG.md has no '## {v}' section")
cur = json.loads((ROOT / "skills.json").read_text(encoding="utf-8")) if (ROOT / "skills.json").exists() else {}
if "--fix" in sys.argv:
    (ROOT / "skills.json").write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8", newline="\n")
elif cur != reg:
    errors.append("skills.json is out of date: run python tools/release_check.py --fix")
print("\n".join(errors) or f"ok: {len(reg)} skills")
sys.exit(1 if errors else 0)
