"""Syncs the skills YOU created on any device (Hermes "local" skills) to all your devices.

Bundled skills (shipped with Hermes) and hub-installed skills are NOT copied: every device gets those
from Hermes itself. Only skills you or your Hermes created (skill_manage) travel, file by file.

Three-way per file, like the memory merge:
  base   = hash of the file at the last sync on THIS device (cache/hermes-sync-skills-base.json)
  changed only here     -> copied to the repo
  changed only remotely -> copied to this device
  changed on both       -> the newer file wins (the other is kept as <file>.conflict-<device>)
  deleted on one side (and unchanged on the other) -> deleted on both
Usage as a module: run(skills_dir, repo_dir, base_file, device_name) -> list of messages.
"""
import hashlib, json, os, shutil, time
from pathlib import Path

SKIP_DIRS = {".hub", ".locks", "__pycache__"}


def _h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _excluded(skills_dir):
    """Names of bundled + hub-installed skills (those are managed by Hermes, never synced)."""
    names = set()
    try:
        for line in (skills_dir / ".bundled_manifest").read_text(encoding="utf-8").splitlines():
            if ":" in line:
                names.add(line.split(":", 1)[0].strip())
    except OSError:
        pass
    try:
        lock = json.loads((skills_dir / ".hub" / "lock.json").read_text(encoding="utf-8"))
        names |= set((lock.get("installed") or {}).keys())
    except (OSError, ValueError):
        pass
    return names


def _skill_name(skill_dir):
    try:
        for line in (skill_dir / "SKILL.md").read_text(encoding="utf-8").splitlines()[1:30]:
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip().strip("'\"")
            if line.strip() == "---":
                break
    except OSError:
        pass
    return skill_dir.name


def _local_skill_dirs(skills_dir):
    """Relative paths (posix) of skill folders that hold user-created skills."""
    out, excl = set(), _excluded(skills_dir)
    for md in skills_dir.rglob("SKILL.md"):
        d = md.parent
        rel = d.relative_to(skills_dir)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts):
            continue
        if _skill_name(d) in excl or d.name in excl:
            continue
        out.add(rel.as_posix())
    return out


def _files(root, rels):
    res = {}
    for rel in rels:
        d = root / rel
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts and ".conflict-" not in f.name:
                res[f.relative_to(root).as_posix()] = f
    return res


def run(skills_dir, repo_dir, base_file, device):
    skills_dir, repo_dir, base_file = Path(skills_dir), Path(repo_dir), Path(base_file)
    repo_dir.mkdir(parents=True, exist_ok=True)
    try:
        base = json.loads(base_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        base = {}
    msgs = []
    local_dirs = _local_skill_dirs(skills_dir)
    repo_dirs = {p.parent.relative_to(repo_dir).as_posix() for p in repo_dir.rglob("SKILL.md")}
    # a skill that is bundled/hub on THIS device must never be overwritten from the repo
    excl = _excluded(skills_dir)
    repo_dirs = {r for r in repo_dirs if Path(r).name not in excl}
    L = _files(skills_dir, local_dirs | {r for r in repo_dirs if (skills_dir / r).is_dir()})
    R = _files(repo_dir, repo_dirs)
    new_base = {}
    for rel in sorted(set(L) | set(R) | set(base)):
        lp, rp = L.get(rel), R.get(rel)
        lh, rh, bh = (_h(lp) if lp else None), (_h(rp) if rp else None), base.get(rel)
        if lh == rh:
            if lh:
                new_base[rel] = lh
            continue
        dst_local, dst_repo = skills_dir / rel, repo_dir / rel
        if lh != bh and rh == bh:          # changed (or created/deleted) only here
            if lh:
                dst_repo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(lp, dst_repo)
                new_base[rel] = lh
            else:
                dst_repo.unlink(missing_ok=True)
        elif rh != bh and lh == bh:        # changed only on another device
            if rh:
                dst_local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rp, dst_local)
                new_base[rel] = rh
                if rel.endswith("/SKILL.md") and not lp:
                    msgs.append(f"new skill from another device: {Path(rel).parent.name}")
            else:
                dst_local.unlink(missing_ok=True)
        else:                              # changed on both sides
            if lh and rh:
                newer_here = lp.stat().st_mtime >= rp.stat().st_mtime
                win, lose = (lp, rp) if newer_here else (rp, lp)
                keep = dst_local.with_name(dst_local.name + f".conflict-{time.strftime('%Y%m%d%H%M')}")
                shutil.copy2(lose, keep)       # the losing version stays on this device, never lost
                for d in (dst_local, dst_repo):
                    if d != win:
                        shutil.copy2(win, d)
                new_base[rel] = _h(win)
                msgs.append(f"skill file changed on two devices, kept the newer one ({keep.name} has the other): {rel}")
            else:                          # deleted on one side, changed on the other: keep it
                src = lp or rp
                for d in (dst_local, dst_repo):
                    if d != src:
                        d.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, d)
                new_base[rel] = _h(src)
    # remove empty folders left by deletions
    for root in (skills_dir, repo_dir):
        for d in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(d.iterdir()) and not any(part.startswith(".") for part in d.relative_to(root).parts):
                try:
                    d.rmdir()
                except OSError:
                    pass
    base_file.parent.mkdir(parents=True, exist_ok=True)
    base_file.write_text(json.dumps(new_base, indent=1), encoding="utf-8")
    return msgs
