"""Request queue between devices: leave work for a device that is off or far away.

  python jobs.py add "<device>" "what to do"   create a request (then sync to push it)
  python jobs.py list                          show all requests and their status
  python jobs.py process                       (sync) start requests for this device, report results
  python jobs.py run <id>                      (internal) execute one request with Hermes

A request is <data dir>/queue/<id>.json. The target device starts it on its first sync after it
is switched on with a user logged in, runs it with `hermes chat --oneshot` (normal model chain,
no confirmations because nobody is there to answer), and writes <id>.result.md. The device that
created it prints "hermes-sync: request ... done" on a later sync.
Sessions created by requests start with QUEUE_PREFIX, so the conversation hand-off skips them.
"""
import json, os, subprocess, sys, time
from pathlib import Path
from common import HH, data_dir, device, shared_cfg, hermes_bin, read_json, write_json, out, strip_ansi

QUEUE_PREFIX = "[hermes-sync queued request]"


def qdir():
    d = data_dir() / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def known_devices():
    return sorted(read_json(p, {}).get("device") or p.stem for p in (data_dir() / "devices").glob("*.json"))


def add(target, task):
    devs = known_devices()
    if devs and target not in devs:
        out(f"unknown device '{target}'. Known devices: {', '.join(devs)}")
        sys.exit(2)
    src = device()
    jid = time.strftime("%Y%m%d-%H%M%S") + "-" + "".join(c for c in src.lower() if c.isalnum())[:16]
    write_json(qdir() / f"{jid}.json", {"id": jid, "from": src, "to": target, "task": task,
                                        "created": now(), "status": "pending"})
    out(f"request {jid} created for {target}. It is pushed on the next sync.")
    print(jid)


def lst():
    for p in sorted(qdir().glob("*.json")):
        d = read_json(p, {})
        print(f"{d.get('id')} | {d.get('from')} -> {d.get('to')} | {d.get('status')} | {d.get('task', '')[:70]}")


def process():
    me = device()
    max_s = float(shared_cfg()["queue"].get("max_hours", 3)) * 3600
    seen_f = HH / "cache" / "hermes-sync-results-seen.json"
    seen = read_json(seen_f, [])
    for p in sorted(qdir().glob("*.json")):
        d = read_json(p, {})
        if d.get("to") == me and d.get("status") == "pending":
            d.update(status="running", started=now(), started_ts=time.time())
            write_json(p, d)
            flags = (0x08000000 | 0x00000200) if os.name == "nt" else 0  # CREATE_NO_WINDOW | NEW_PROCESS_GROUP (no console windows)
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "run", d["id"]],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags, close_fds=True, start_new_session=(os.name != "nt"))
            out(f"running request {d['id']} from {d['from']}: {d['task'][:80]}")
        elif d.get("to") == me and d.get("status") == "running" and time.time() - d.get("started_ts", 0) > max_s:
            d.update(status="failed", finished=now(), error="took too long, or the device was switched off mid-run")
            write_json(p, d)
        if d.get("from") == me and d.get("status") in ("done", "failed") and d.get("id") not in seen:
            out(f"request to {d['to']} {d['status']}: '{d['task'][:60]}' -> {qdir() / (d['id'] + '.result.md')}")
            seen.append(d["id"])
    write_json(seen_f, seen)


def run(jid):
    p = qdir() / f"{jid}.json"
    d = read_json(p)
    rules = shared_cfg()["queue"].get("rules") or ""
    prompt = (f"{QUEUE_PREFIX} Request left by the user on device '{d['from']}' at {d['created']}, to be done here "
              f"on '{d['to']}' while the user is NOT present. If something needs the user's decision, a password "
              f"or spending money, stop and explain what is missing instead of guessing. "
              f"{rules}\nWhen finished, reply briefly in the user's language: what you did and what is left.\n\n"
              f"REQUEST:\n{d['task']}")
    try:
        r = subprocess.run([hermes_bin(), "chat", "-q", prompt, "--oneshot", "-Q", "--yolo"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=float(shared_cfg()["queue"].get("max_hours", 3)) * 3600,
                           cwd=str(Path.home()), stdin=subprocess.DEVNULL)
        text = strip_ansi((r.stdout or "").strip() or (r.stderr or "").strip()[-3000:])
        text = "\n".join(l for l in text.splitlines() if not l.startswith("session_id:")).strip()
        ok = r.returncode == 0 and bool((r.stdout or "").strip())
    except Exception as e:  # noqa: BLE001
        text, ok = f"could not run Hermes: {e}", False
    (qdir() / f"{jid}.result.md").write_text(
        f"# Request {jid}\n\n{d['from']} -> {d['to']}, created {d['created']}, finished {now()}\n\n"
        f"## Request\n{d['task']}\n\n## Result\n{text}\n", encoding="utf-8", newline="\n")
    d = read_json(p)
    d.update(status="done" if ok else "failed", finished=now())
    write_json(p, d)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["add"] and len(a) == 3:
        add(a[1], a[2])
    elif a[:1] == ["list"]:
        lst()
    elif a[:1] == ["process"]:
        process()
    elif a[:1] == ["run"] and len(a) == 2:
        run(a[1])
    else:
        print(__doc__)
