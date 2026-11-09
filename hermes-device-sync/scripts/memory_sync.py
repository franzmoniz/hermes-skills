"""Merges Hermes memory (memories/MEMORY.md and USER.md) across devices.

Three-way merge per entry (entries are separated by a line with only "§", the Hermes format):
  base   = last version synced on THIS device ($HERMES_HOME/cache/hermes-sync-memory-base/)
  local  = $HERMES_HOME/memories/<file>
  remote = <data dir>/memory/<file> (already updated by git pull)
An entry stays if both sides have it or one side added it; it goes if one side deleted/changed it.
First sync on a device = union of both sides (nothing is lost). Silent when all is well.
"""
import os, re
from common import HH, data_dir

FILES = ["MEMORY.md", "USER.md"]
SEP = re.compile(r"\r?\n§\r?\n")


def _read(p):
    try:
        with open(p, encoding="utf-8", newline="") as f:
            return f.read()
    except OSError:
        return None


def _entries(text):
    if not text or not text.strip():
        return []
    return [e.strip() for e in SEP.split(text.strip()) if e.strip()]


def _norm(e):
    return e.replace("\r\n", "\n")


def _render(items, crlf):
    nl = "\r\n" if crlf else "\n"
    return (nl + "§" + nl).join(_norm(e).replace("\n", nl) for e in items)


def _write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".sync-tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, p)


def merge(base, local, remote):
    if base is None:
        out = list(remote)
        seen = {_norm(e) for e in out}
        return out + [e for e in local if _norm(e) not in seen]
    B, L, R = ({_norm(e) for e in x} for x in (base, local, remote))
    keep = lambda e: (e in L and e in R) or (e in L and e not in B) or (e in R and e not in B)
    out, seen = [], set()
    for e in list(remote) + list(local):
        n = _norm(e)
        if n not in seen and keep(n):
            out.append(e)
            seen.add(n)
    return out


def run():
    for f in FILES:
        lp = str(HH / "memories" / f)
        rp = str(data_dir() / "memory" / f)
        bp = str(HH / "cache" / "hermes-sync-memory-base" / f)
        lt, rt, bt = _read(lp), _read(rp), _read(bp)
        if lt is None and rt is None:
            continue
        crlf = "\r\n" in (lt or "") or os.name == "nt"
        L, R = _entries(lt), _entries(rt)
        merged = merge(None if bt is None else _entries(bt), L, R)
        if [_norm(e) for e in merged] != [_norm(e) for e in L]:
            _write(lp, _render(merged, crlf))
        if rt is None or [_norm(e) for e in merged] != [_norm(e) for e in R]:
            _write(rp, _render(merged, False))
        _write(bp, _render(merged, False))


if __name__ == "__main__":
    run()
