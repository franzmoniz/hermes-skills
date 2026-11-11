"""Moves your newest Hermes conversation between devices through the sync repo.

  python handoff.py export      export this device's newest conversation (sync runs this)
  python handoff.py pick        if another device has a newer conversation, import it and print its
                                session id (run by the `hermes` launcher before Hermes opens)
  python handoff.py activity    update this conversation's line in the activity log (activity.md)

Which conversation: with the skill Hermes's Terminal installed, the conversation "Hermes's Terminal"
(an imported one is handed to it with `terminal.py adopt`, so `hermes` continues it, recap included).
Without it, the newest terminal conversation (it then shows up in /resume on the other device).

Conversations live on a separate branch (config "sessions_branch"), one file per device, always
replaced (the branch is rewritten without history, so it never grows). Export only happens when
the last answer has finished. Export/import use no model (zero tokens); only the optional recap does.
Relies on Hermes internals (state.db, `hermes sessions export/import`): if a Hermes update breaks
them, the sync keeps working and only the hand-off is skipped (an error line is printed).
"""
import importlib.util, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, time
from common import HH, device, shared_cfg, git, hermes_bin, out, read_json, write_json
from jobs import QUEUE_PREFIX

STATE = HH / "cache" / "hermes-sync-handoff.json"
BRANCH = shared_cfg().get("sessions_branch") or "hermes-sessions"


def load_state():
    s = read_json(STATE, None) or {}
    for k in ("exported", "imported", "sessions"):
        s.setdefault(k, {})
    return s


def save_state(s):
    write_json(STATE, s)


def effective_ts(st, sid, ts):
    """Imported conversations get the import time; keep the original time until someone writes in them."""
    info = st["sessions"].get(sid)
    if info and ts <= info["at"] + 120:
        return info["src_ts"], True
    return ts, False


def db():
    return sqlite3.connect("file:" + str(HH / "state.db") + "?mode=ro", uri=True, timeout=10)


def terminal():
    """The Hermes's Terminal module when that skill is installed on this device, else None."""
    script = (read_json(HH / "hermes-terminal.json", {}) or {}).get("script")
    if not script or not os.path.exists(script):
        return None
    try:
        spec = importlib.util.spec_from_file_location("hermes_terminal", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def terminal_recap(sid):
    t = terminal()
    return t.state()["summaries"].get(sid, {}).get("text", "") if t and sid else ""


def latest_session():
    """(id, last_ts, last_role, last_content, last_tool_calls) of the conversation to move between devices:
    "Hermes's Terminal" when that skill is installed, else the newest local CLI conversation."""
    if not (HH / "state.db").exists():
        return None  # no conversations on this device yet
    c = db()
    t = terminal()
    sid = t.current() if t else None
    if sid:
        ts = c.execute("SELECT MAX(timestamp) FROM messages WHERE session_id=?", (sid,)).fetchone()[0]
        if ts is not None:
            last = c.execute("SELECT role, content, tool_calls FROM messages WHERE session_id=? "
                             "ORDER BY timestamp DESC, id DESC LIMIT 1", (sid,)).fetchone()
            return (sid, ts) + tuple(last)
    row = c.execute(
        "SELECT s.id, MAX(m.timestamp) t FROM sessions s JOIN messages m ON m.session_id = s.id "
        "WHERE s.source IN ('local','cli') AND COALESCE(s.created_source,'cli') != 'desktop' "
        "AND COALESCE(s.archived,0)=0 AND COALESCE(s.hidden,0)=0 "
        "AND NOT EXISTS (SELECT 1 FROM messages f WHERE f.session_id = s.id AND f.role = 'user' "
        "AND f.content LIKE ?) "
        "GROUP BY s.id ORDER BY t DESC LIMIT 1", (QUEUE_PREFIX + "%",)).fetchone()
    if not row:
        return None
    last = c.execute("SELECT role, content, tool_calls FROM messages WHERE session_id=? "
                     "ORDER BY timestamp DESC, id DESC LIMIT 1", (row[0],)).fetchone()
    return (row[0], row[1]) + tuple(last)


def remote_sha():
    git("fetch", "-q", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (BRANCH, BRANCH), check=False)
    return git("rev-parse", "-q", "--verify", "refs/remotes/origin/" + BRANCH, check=False)


def export():
    s = latest_session()
    if not s:
        return
    sid, ts, role, content, tool_calls = s
    if role != "assistant" or not (content or "").strip() or tool_calls:
        return  # the answer is not finished yet: next round
    st = load_state()
    summ = terminal_recap(sid)
    if st["exported"].get(sid) == ts and st.get("exported_summary", "") == summ:
        return
    ts, untouched_import = effective_ts(st, sid, ts)
    if untouched_import:
        return  # it is just another device's conversation, nothing new from here
    dev = device()
    tmp = tempfile.mkdtemp()
    try:
        f = os.path.join(tmp, "s.jsonl")
        r = subprocess.run([hermes_bin(), "sessions", "export", "--format", "trace", "--session-id", sid,
                            "--yes", f], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if r.returncode or not os.path.exists(f):
            out("conversation export failed: " + (r.stderr or r.stdout)[-300:])
            return
        meta = os.path.join(tmp, "m.json")
        json.dump({"device": dev, "session_id": sid, "last_ts": ts, "summary": summ,
                   "exported_at": time.time()}, open(meta, "w", encoding="utf-8"))
        for _ in range(3):
            base = remote_sha()
            env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"))
            git("read-tree", base if base else "--empty", env=env)
            for src, name in ((f, dev + ".jsonl"), (meta, dev + ".json")):
                blob = git("hash-object", "-w", src)
                git("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, name), env=env)
            commit = git("commit-tree", git("write-tree", env=env), "-m", "conversation of %s" % dev)
            lease = "--force-with-lease=refs/heads/%s:%s" % (BRANCH, base or "")
            r = subprocess.run(["git", "-C", str(git("rev-parse", "--show-toplevel")), "push", "-q", lease,
                                "origin", "%s:refs/heads/%s" % (commit, BRANCH)], capture_output=True, text=True)
            if r.returncode == 0:
                st["exported"] = {sid: s[1]}
                st["exported_summary"] = summ
                save_state(st)
                return
            time.sleep(2)
        out("conversation push failed: " + r.stderr[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


NOISE = re.compile(r"^\s*(\[ran tool: [^\]]*\]|\[Image attached at: .*\]|\[screenshot\])\s*$")
SYSTEM_MSG = ("[IMPORTANT: Background process", "[INTERNAL NOTIFICATION")
HEADERS = ("[Context from the interrupted assistant response]", "[This response was interrupted by a user correction.]")


def clean(t):
    t = (t or "").strip()
    if t.startswith(SYSTEM_MSG):
        return ""
    lines = [l for l in t.splitlines() if not NOISE.match(l) and l.strip() not in HEADERS]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def clean_trace(data):
    """Keeps only the conversation text (drops tool calls/results and system notices) and merges
    consecutive messages from the same side so roles always alternate user/assistant."""
    res = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        x = json.loads(line)
        c = (x.get("message") or {}).get("content")
        text = ("\n\n".join(b.get("text", "") for b in c if b.get("type") == "text") if isinstance(c, list)
                else (c or "")).strip()
        if x.get("type") == "user":
            text = clean(text)
        if not text:
            continue
        if res and res[-1].get("type") == x.get("type"):
            if x.get("type") == "user":
                res[-1]["_text"] += "\n\n" + text
            else:
                res[-1]["_text"] = text  # keep only the final answer of the assistant turn
            continue
        x["_text"] = text
        res.append(x)
    for x in res:
        t = x.pop("_text")
        x["message"]["content"] = t if x.get("type") == "user" else [{"type": "text", "text": t}]
    return ("\n".join(json.dumps(x, ensure_ascii=False) for x in res) + "\n").encode("utf-8")


def pick():
    if not remote_sha():
        return
    dev = device()
    best = None
    for n in git("ls-tree", "--name-only", "refs/remotes/origin/" + BRANCH).splitlines():
        if not n.endswith(".json") or n == dev + ".json":
            continue
        m = json.loads(git("show", "refs/remotes/origin/%s:%s" % (BRANCH, n)))
        if not best or m["last_ts"] > best["last_ts"]:
            best = m
    if not best:
        return
    local = latest_session()
    st = load_state()
    if local and effective_ts(st, local[0], local[1])[0] >= best["last_ts"]:
        return  # the conversation here is the newest
    if st["imported"].get(best["device"]) == best["last_ts"]:
        return  # already imported
    tmp = tempfile.mkdtemp()
    try:
        f = os.path.join(tmp, "s.jsonl")
        data = subprocess.run(["git", "-C", str(git("rev-parse", "--show-toplevel")), "show",
                               "refs/remotes/origin/%s:%s.jsonl" % (BRANCH, best["device"])], capture_output=True).stdout
        open(f, "wb").write(clean_trace(data))
        r = subprocess.run([hermes_bin(), "sessions", "import", "--from", "claude", f],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        m = re.search(r"session as (\S+)", r.stdout or "")
        if not m:
            print("hermes-sync: conversation import failed: " + (r.stderr or r.stdout)[-300:], file=sys.stderr)
            return
        st["imported"][best["device"]] = best["last_ts"]
        st["sessions"][m.group(1)] = {"src_ts": best["last_ts"], "at": time.time(), "from": best["device"]}
        save_state(st)
        t = terminal()
        if t:  # Hermes's Terminal installed: this becomes "Hermes's Terminal" here, with the other device's recap
            sf = os.path.join(tmp, "recap.txt")
            open(sf, "w", encoding="utf-8").write(best.get("summary") or "")
            t.adopt(m.group(1), sf)
        print(m.group(1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def activity(sid=None):
    """Activity log <data dir>/activity.md: ONE line per conversation, placed by the time the conversation
    happened (so work done offline days ago lands days back), replaced on every answer, never one line per
    message. Text = the Hermes's Terminal recap if there is one, else the conversation title, else the
    first request."""
    from common import data_dir
    import timeline
    if not (HH / "state.db").exists():
        return  # no conversations on this device yet
    c = db()
    if not sid:
        s = latest_session()
        if not s:
            return
        sid = s[0]
    row = c.execute("SELECT MAX(timestamp) FROM messages WHERE session_id=?", (sid,)).fetchone()
    if not row or row[0] is None:
        return
    ts = row[0]
    text = terminal_recap(sid).strip()
    if not text:
        r = c.execute("SELECT title FROM sessions WHERE id=?", (sid,)).fetchone()
        text = (r[0] if r and r[0] else "") or ""
        if not text:
            f = c.execute("SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY timestamp, id LIMIT 1",
                          (sid,)).fetchone()
            text = " ".join(clean(f[0] if f else "").split())[:160]
        text = text or "conversation"
    text = " ".join(l.strip().rstrip(".") + "." for l in text.splitlines() if l.strip())
    mark = f"<!-- session:{sid} -->"
    p = data_dir() / "activity.md"
    if not p.exists():
        p.write_text("# Activity\n\nOne line per Hermes conversation, newest first (written automatically).\n",
                     encoding="utf-8", newline="\n")
    timeline.upsert(p, f"- {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))} | {device()} | {text} {mark}", mark)


def catchup():
    """Run by sync after a successful pull (= online): tidy the activity log after merges (duplicates out,
    sorted by date); with Hermes's Terminal, refresh the line once a recap left pending offline exists."""
    from common import data_dir
    import timeline
    timeline.normalize(data_dir() / "activity.md")
    t = terminal()
    if t and t.current():
        try:
            t.summarize(t.current())
            activity(t.current())
        except Exception:
            pass


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    fn = {"export": export, "pick": pick, "activity": activity, "catchup": catchup}.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(1)
    fn()
