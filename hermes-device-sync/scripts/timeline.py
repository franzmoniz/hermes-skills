"""Activity log with one line per conversation, ordered by WHEN the conversation happened (not by when it
arrived): a conversation held offline 3 days ago lands 3 days back, not on top.
  upsert(path, line, mark)  replace the line carrying `mark` (or add it) at the right place by date
  normalize(path)           after a merge: drop duplicates (same mark, newest wins) and sort by date
Dated lines look like "- YYYY-MM-DD HH:MM | ...". Newest first.
"""
import re
from pathlib import Path

DATED = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ")
MARK = re.compile(r"<!-- (?:sessao|session):\S+ -->")


def _read(p):
    raw = Path(p).read_bytes().decode("utf-8") if Path(p).exists() else ""
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.split(nl) if raw else [], nl


def _write(p, lines, nl):
    data = nl.join(lines)
    if not data.endswith(nl):
        data += nl
    old = Path(p).read_bytes().decode("utf-8") if Path(p).exists() else None
    if old != data:
        Path(p).write_bytes(data.encode("utf-8"))


def _key(line):
    m = DATED.match(line)
    return m.group(1) if m else ""


def _sorted_block(lines):
    """header (before the first dated line) + dated lines sorted desc without duplicates + the rest."""
    first = next((i for i, l in enumerate(lines) if DATED.match(l)), None)
    if first is None:
        return lines
    head, dated, rest, seen = lines[:first], [], [], {}
    for l in lines[first:]:
        if DATED.match(l):
            m = MARK.search(l)
            if m:
                k = m.group(0)
                if k in seen:  # duplicate from a merge: keep the newest
                    j = seen[k]
                    if _key(l) >= _key(dated[j]):
                        dated[j] = l
                    continue
                seen[k] = len(dated)
            dated.append(l)
        elif l.strip():
            rest.append(l)
    dated.sort(key=_key, reverse=True)  # stable: same-minute lines keep their order
    out = head + dated
    if rest:
        out += [""] + rest
    return out


def upsert(path, line, mark):
    lines, nl = _read(path)
    lines = [l for l in lines if mark not in l]
    first = next((i for i, l in enumerate(lines) if DATED.match(l)), None)
    if first is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(line)
    else:
        lines.insert(first, line)
    _write(path, _sorted_block(lines), nl)


def normalize(path):
    if not Path(path).exists():
        return
    lines, nl = _read(path)
    _write(path, _sorted_block(lines), nl)
