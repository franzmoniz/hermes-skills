"""Moves your newest Hermes conversation between devices through the sync repo.

  python handoff.py export      export this device's newest conversation (sync runs this)
  python handoff.py pick        if another device has a newer conversation, import it and
                                print its session id (the `hermes` wrapper then resumes it)
  python handoff.py summarize   write a 3-line recap of the newest conversation (optional, see config)
  python handoff.py prepare <id> put that recap in the "Previous Conversation" panel of Hermes
  python handoff.py activity    update this conversation's line in the activity log (activity.md)

Conversations live on a separate branch (config "sessions_branch"), one file per device, always
replaced (the branch is rewritten without history, so it never grows). Export only happens when
the last answer has finished. Export/import use no model (zero tokens); only the optional recap does.
Relies on Hermes internals (state.db, `hermes sessions export/import`): if a Hermes update breaks
them, the sync keeps working and only the hand-off is skipped (an error line is printed).
"""
import json, os, re, shutil, sqlite3, subprocess, sys, tempfile, time
from common import HH, device, shared_cfg, git, hermes_bin, out, read_json, write_json
from jobs import QUEUE_PREFIX

STATE = HH / "cache" / "hermes-sync-handoff.json"
BRANCH = shared_cfg().get("sessions_branch") or "hermes-sessions"


def load_state():
    s = read_json(STATE, None) or {}
    for k in ("exported", "imported", "sessions", "summaries"):
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


def latest_session():
    """(id, last_ts, last_role, last_content, last_tool_calls) of the newest local CLI conversation."""
    if not (HH / "state.db").exists():
        return None  # no conversations on this device yet
    c = db()
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
    summ = st["summaries"].get(sid, {}).get("text", "")
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
        if best.get("summary"):
            st["summaries"][m.group(1)] = {"ts": time.time(), "text": best["summary"]}
        save_state(st)
        print(m.group(1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- optional 3-line recap for the "Previous Conversation" panel ----------

def _hermes_imports():
    """Puts the Hermes code and its Python environment on sys.path (to use its auxiliary LLM client)."""
    import glob
    agent_dir = str(HH / "hermes-agent")
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    for f in glob.glob(str(HH / "installs" / "*" / "facts.json")):
        try:
            env = json.load(open(f, encoding="utf-8"))["packages"]["venv"]["environment"]
        except Exception:
            continue
        for sp in (os.path.join(env, "Lib", "site-packages"), *glob.glob(os.path.join(env, "lib", "python3*", "site-packages"))):
            if os.path.isdir(sp) and sp not in sys.path:
                sys.path.insert(1, sp)
    os.environ.setdefault("HERMES_HOME", str(HH))


def summarize():
    cfg = shared_cfg()["summary"]
    if not cfg.get("enabled") or not cfg.get("provider"):
        return
    s = latest_session()
    if not s:
        return
    sid, ts = s[0], s[1]
    st = load_state()
    if st["summaries"].get(sid, {}).get("ts", 0) >= ts:
        return
    rows = db().execute("SELECT role, content, tool_calls FROM messages WHERE session_id=? AND role IN ('user','assistant') "
                        "ORDER BY timestamp, id", (sid,)).fetchall()
    msgs = [(r, clean(t)) for r, t, tc in rows if (t or "").strip() and not (r == "assistant" and tc)]
    msgs = [m for m in msgs if m[1]][-14:]
    if not msgs:
        return
    conv = "\n\n".join(("USER: " if r == "user" else "HERMES: ") + t[:1500] for r, t in msgs)
    prompt = (f"Summarize in {cfg.get('language') or 'English'}, in at most 3 short lines (about 90 characters each), "
              "what this conversation between the user and the Hermes assistant is about and where it stopped, "
              "so the user remembers when resuming. No markdown, no introduction, one idea per line.")
    _hermes_imports()
    import io, contextlib, logging
    logging.disable(logging.WARNING)
    try:
        from agent.auxiliary_client import call_llm
        with contextlib.redirect_stderr(io.StringIO()):
            r = call_llm(provider=cfg["provider"], model=cfg.get("model") or None,
                         messages=[{"role": "system", "content": prompt}, {"role": "user", "content": conv}],
                         max_tokens=1000, temperature=None, timeout=60, reasoning_config={"enabled": False})
        text = (r.choices[0].message.content or "").strip()
    except Exception:
        text = ""
    if not text:
        return
    st["summaries"][sid] = {"ts": ts, "text": "\n".join([l.strip(" -*\t") for l in text.splitlines() if l.strip()][:3])}
    save_state(st)


MARK = "# Generated by hermes-device-sync (recap of the last conversation). Do not edit."


def activity():
    """Activity log <data dir>/activity.md: ONE line per conversation (newest first), replaced on every
    answer, never one line per message. Uses the recap if enabled, else the conversation title, else
    the first request. Lets the user (and every device's Hermes) see what was done where."""
    from common import data_dir
    s = latest_session()
    if not s:
        return
    sid, ts = s[0], s[1]
    text = load_state()["summaries"].get(sid, {}).get("text", "").strip()
    if not text:
        c = db()
        row = c.execute("SELECT title FROM sessions WHERE id=?", (sid,)).fetchone()
        text = (row[0] if row and row[0] else "") or ""
        if not text:
            first = c.execute("SELECT content FROM messages WHERE session_id=? AND role='user' "
                              "ORDER BY timestamp, id LIMIT 1", (sid,)).fetchone()
            text = clean(first[0] if first else "")[:160]
    text = " ".join(l.strip().rstrip(".") + "." for l in text.splitlines() if l.strip())
    if not text:
        return
    mark = f"<!-- session:{sid} -->"
    line = f"- {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))} | {device()} | {text} {mark}"
    p = data_dir() / "activity.md"
    head = "# Activity\n\nOne line per Hermes conversation, newest first (written automatically).\n"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else head.splitlines()
    old = next((i for i, l in enumerate(lines) if mark in l), None)
    if old is not None:
        if lines[old] == line:
            return
        del lines[old]
    i = next((k for k, l in enumerate(lines) if l.startswith("- ")), len(lines))
    if i == len(lines) and lines and lines[-1].strip():
        lines.append("")
        i += 1
    lines.insert(i, line)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def prepare(sid=""):
    """Writes the recap into the Hermes locale overlay key cli.resume.earlier_messages (shown above the
    resumed conversation). Never touches an en.yaml overlay that hermes-device-sync did not create."""
    path = HH / "locales" / "en.yaml"
    if path.exists() and not path.read_text(encoding="utf-8").startswith(MARK):
        return
    if not sid:
        s = latest_session()
        sid = s[0] if s else ""
    summ = load_state()["summaries"].get(sid, {}).get("text", "")
    if not summ:
        if path.exists():
            path.unlink()
        return
    body = "Recap:\n" + "\n".join("    " + l.replace("{", "{{").replace("}", "}}") for l in summ.splitlines())
    body += "\n\n  ... {count} earlier messages ..."
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MARK + "\ncli:\n  resume:\n    earlier_messages: " + json.dumps(body, ensure_ascii=False) + "\n",
                    encoding="utf-8")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    fn = {"export": export, "pick": pick, "summarize": summarize, "prepare": prepare, "activity": activity}.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(1)
    fn(*args[:1]) if cmd == "prepare" else fn()
