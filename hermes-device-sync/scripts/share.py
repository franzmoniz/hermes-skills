"""Share files between your devices through the sync repo (when there is no better way).

  python share.py put <file> [note]    copy a file into the shared folder (pushed on the next sync)
  python share.py list                 list shared files (who shared, when, note)
  python share.py get <name> [dest]    copy a shared file to dest (default: your Downloads folder)
  python share.py rm <name>            remove a shared file (from every device on the next sync)

Prefer a cloud drive both devices are logged in to (Google Drive, OneDrive, Dropbox...): it has no
size limit worth worrying about and does not grow the git history. Use this folder for small files
(limit 50 MB per file; GitHub rejects files over 100 MB, and every shared file stays in the repo
history until you clean it). If the file is on ANOTHER device, leave that device a request
(jobs.py add "<device>" "share the file ... with share.py put") and it uploads it when it is on.
"""
import shutil, sys, time
from pathlib import Path
from common import data_dir, device, read_json, write_json, out

MAX_MB = 50


def sdir():
    d = data_dir() / "shared"
    d.mkdir(parents=True, exist_ok=True)
    return d


def index():
    return read_json(sdir() / "index.json", {})


def put(path, note=""):
    p = Path(path).expanduser()
    if not p.is_file():
        out(f"not a file: {p}")
        return 2
    mb = p.stat().st_size / 1e6
    if mb > MAX_MB:
        out(f"{p.name} has {mb:.0f} MB (limit {MAX_MB} MB). Use a cloud drive both devices are logged in to.")
        return 2
    shutil.copy2(p, sdir() / p.name)
    idx = index()
    idx[p.name] = {"from": device(), "at": time.strftime("%Y-%m-%d %H:%M"), "mb": round(mb, 2), "note": note}
    write_json(sdir() / "index.json", idx)
    out(f"shared {p.name} ({mb:.2f} MB). It reaches the other devices on the next sync.")
    return 0


def lst():
    for name, i in sorted(index().items()):
        print(f"{name} | from {i.get('from')} | {i.get('at')} | {i.get('mb')} MB | {i.get('note', '')}")


def get(name, dest=None):
    src = sdir() / name
    if not src.exists():
        out(f"no shared file named {name} (run a sync first if it was just shared)")
        return 2
    d = Path(dest).expanduser() if dest else Path.home() / "Downloads"
    d.mkdir(parents=True, exist_ok=True)
    target = d / name if d.is_dir() else d
    shutil.copy2(src, target)
    print(target)
    return 0


def rm(name):
    (sdir() / name).unlink(missing_ok=True)
    idx = index()
    idx.pop(name, None)
    write_json(sdir() / "index.json", idx)
    out(f"removed {name} (from every device on the next sync)")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["put"] and len(a) in (2, 3):
        sys.exit(put(a[1], a[2] if len(a) == 3 else ""))
    elif a[:1] == ["list"]:
        lst()
    elif a[:1] == ["get"] and len(a) in (2, 3):
        sys.exit(get(a[1], a[2] if len(a) == 3 else None))
    elif a[:1] == ["rm"] and len(a) == 2:
        sys.exit(rm(a[1]))
    else:
        print(__doc__)
