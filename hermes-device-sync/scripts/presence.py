"""One Hermes at a time: warns when Hermes is already open on another of your devices.

  python presence.py start            (the `hermes` wrapper) before opening Hermes here: checks the
                                      other devices; if one has Hermes open, asks you:
                                        1 = close Hermes on that device and continue here
                                        2 = close this terminal (keep using the other device)
                                      Exit code 0 = go on, 3 = the user chose to stop here.
                                      Then marks this device as "Hermes open" and syncs.
  python presence.py stop             (the `hermes` wrapper) after Hermes closes: marks it closed.
  python presence.py status           Hermes open/closed on every device.
  python presence.py guard "<device>" for Hermes itself, BEFORE opening Hermes on another device
                                      (remote checks, queued work): looks at the request queue and
                                      the queue rules first, then at whether Hermes is open there.
                                      Prints "free", or "busy: ..." (exit code 3) so Hermes asks you.
  python presence.py close "<device>" closes the Hermes open on <device> (over SSH) and waits until
                                      that device has saved the conversation.
  python presence.py local            (internal, run over SSH) prints this device's state as JSON.
  python presence.py heartbeat        (sync) keeps this device's state fresh; clears it after a crash.

How it knows: the wrapper writes $HERMES_HOME/cache/hermes-sync-open.json (wrapper process id) and
<data dir>/devices/<device>.presence.json (pushed by the sync). When a device is reachable over SSH
(remote.py), its real state is asked live; otherwise the pushed file counts while its heartbeat is
recent (STALE_MIN). Queued requests run without the wrapper, so they never count as "Hermes open".
"""
import json, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HH, data_dir, device, read_json, write_json, out, shared_cfg  # noqa: E402

LOCAL = HH / "cache" / "hermes-sync-open.json"
STALE_MIN = 25  # the cron sync refreshes the heartbeat every 15 min
CHOICE_ENV = "HERMES_SYNC_PRESENCE_CHOICE"  # tests / non-interactive use: "1" or "2"


MSG = {
    "en": {"open": "Device {n} has Hermes open{since}{unconfirmed}.", "since": " (since {s})",
           "unconfirmed": " - can't reach it right now to confirm",
           "opt1": "  1 = close Hermes on {n} and continue here", "opt2": "  2 = close this terminal (keep using the other device)",
           "choose": "Choose 1 or 2: ", "cant_close": "can't close Hermes on {n} from here (not reachable over the network/SSH). "
           "Continuing here; close it there when you are back on that device.",
           "closing": "closing Hermes on {n} and saving its conversation...", "closed": "{n}: Hermes closed, conversation saved.",
           "not_open": "{n}: Hermes is not open any more", "no_confirm": "{n}: did not confirm within {w}s; continuing anyway.",
           "rules": "queue rules: ", "busy_job": "busy: request {i} ({st}) is queued/running on {n}: {t}",
           "busy_open": "busy: Hermes is open on {n}{since} ({how})", "this": "this", "isopen": "open", "isclosed": "closed"},
    "pt": {"open": "O dispositivo {n} tem o Hermes ligado{since}{unconfirmed}.", "since": " (desde {s})",
           "unconfirmed": " - nao o consigo contactar agora para confirmar",
           "opt1": "  1 = fechar o Hermes no {n} e usar aqui", "opt2": "  2 = fechar este terminal (continuas no outro dispositivo)",
           "choose": "Escolhe 1 ou 2: ", "cant_close": "nao consigo fechar o Hermes no {n} a partir daqui (sem rede/SSH). "
           "Continuo aqui; fecha-o la quando voltares a esse dispositivo.",
           "closing": "a fechar o Hermes no {n} e a guardar a conversa de la...", "closed": "{n}: Hermes fechado e conversa guardada.",
           "not_open": "{n}: o Hermes ja nao esta ligado", "no_confirm": "{n}: nao confirmou em {w}s; continuo na mesma.",
           "rules": "regras da fila: ", "busy_job": "busy: pedido {i} ({st}) em fila/a correr no {n}: {t}",
           "busy_open": "busy: o Hermes esta ligado no {n}{since} ({how})", "this": "este", "isopen": "ligado", "isclosed": "desligado"},
}


def T(key, **kw):
    lang = str((shared_cfg().get("summary") or {}).get("language") or shared_cfg().get("language") or "English").lower()
    return MSG["pt" if lang.startswith(("pt", "portug")) else "en"][key].format(**kw)


def pfile(name):
    return data_dir() / "devices" / f"{name}.presence.json"


def pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True)
        return str(int(pid)) in r.stdout
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def local_state():
    s = read_json(LOCAL, None)
    if s and not pid_alive(s.get("pid")):
        LOCAL.unlink(missing_ok=True)  # the terminal was closed without `stop` (crash, Alt+F4 ...)
        return None
    return s


def publish(state):
    write_json(pfile(device()), {"device": device(), "open": bool(state), "since": (state or {}).get("since"),
                                  "pid": (state or {}).get("pid"), "heartbeat": time.time(),
                                  "heartbeat_h": time.strftime("%Y-%m-%d %H:%M")})


def run_sync():
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "sync.py")])


def others():
    me = device()
    names = set()
    for p in (data_dir() / "devices").glob("*.json"):
        n = p.name[:-len(".presence.json")] if p.name.endswith(".presence.json") else p.stem
        if n != me:
            names.add(n)
    return sorted(names)


def remote_state(name):
    """Live state over SSH: dict, or None when the device can't be reached."""
    import remote
    d = read_json(data_dir() / "devices" / f"{name}.json")
    if not d or not remote.address(d):
        return None
    py = d.get("python") or ("python" if d.get("os") == "windows" else "python3")
    script = Path(d.get("sync_scripts_dir") or "") / "presence.py" if d.get("sync_scripts_dir") else None
    if not script:
        return None
    cmd = f"& '{py}' '{script}' local" if d.get("os") == "windows" else f"'{py}' '{script}' local"
    r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "remote.py"), "run", name],
                       input=cmd, capture_output=True, text=True, timeout=60)
    for line in reversed((r.stdout or "").splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                pass
    return None


def state_of(name):
    """(open?, how we know, since). Live over SSH when possible, else the pushed file if recent."""
    live = remote_state(name)
    if live is not None:
        return bool(live.get("open")), "live", live.get("since")
    p = read_json(pfile(name), None)
    if not p or not p.get("open"):
        return False, "file", None
    fresh = time.time() - float(p.get("heartbeat") or 0) < STALE_MIN * 60
    return fresh, ("file, not reachable to confirm" if fresh else "file, stale"), p.get("since")


def busy_devices():
    return [(n, how, since) for n in others() for (is_open, how, since) in [state_of(n)] if is_open]


def ask(busy):
    names = ", ".join(n for n, _, _ in busy)
    for n, how, since in busy:
        out(T("open", n=n, since=T("since", s=since) if since else "", unconfirmed="" if how == "live" else T("unconfirmed")))
    print(T("opt1", n=names))
    print(T("opt2"))
    choice = os.environ.get(CHOICE_ENV)
    while choice not in ("1", "2"):
        try:
            choice = input(T("choose")).strip()
        except EOFError:
            choice = "2"
    return choice


def start():
    choice = None
    busy = busy_devices()
    if busy:
        choice = ask(busy)
        if choice == "2":
            return 3
        for n, how, _ in busy:
            if how != "live":
                out(T("cant_close", n=n))
                continue
            close(n)
        run_sync()  # bring in the conversation the other device just saved
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    st = {"pid": int(os.environ.get("HERMES_SYNC_WRAPPER_PID") or os.getppid()), "since": time.strftime("%Y-%m-%d %H:%M")}
    write_json(LOCAL, st)
    publish(st)
    run_sync()
    return 0


def stop():
    LOCAL.unlink(missing_ok=True)
    publish(None)
    return 0


def heartbeat():
    publish(local_state())


def close(name, wait_s=120):
    """Ends the Hermes process started by the wrapper on <name>; its wrapper then saves and syncs."""
    import remote
    d = read_json(data_dir() / "devices" / f"{name}.json") or {}
    live = remote_state(name)
    if not live or not live.get("open"):
        out(T("not_open", n=name))
        return 0
    pid = int(live["pid"])
    if d.get("os") == "windows":
        src = (f"Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}' | "
               "Where-Object { $_.Name -like 'hermes*' -or $_.Name -like 'python*' } | "
               "ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null }")
    else:
        src = f"for c in $(pgrep -P {pid}); do pkill -TERM -P $c; kill -TERM $c; done"
    remote.run(name, src)
    out(T("closing", n=name))
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(5)
        s = remote_state(name)
        if s is not None and not s.get("open"):
            out(T("closed", n=name))
            return 0
    out(T("no_confirm", n=name, w=wait_s))
    return 1


def guard(name):
    """Before Hermes opens Hermes on another device: queue/rules first, then presence."""
    import jobs
    qd = jobs.qdir()
    running = [read_json(p, {}) for p in qd.glob("*.json")]
    running = [j for j in running if j.get("to") == name and j.get("status") in ("pending", "running")]
    rules = (shared_cfg().get("queue") or {}).get("rules") or ""
    if rules:
        print(T("rules") + rules)
    if running:
        for j in running:
            print(T("busy_job", i=j["id"], st=j["status"], n=name, t=j.get("task", "")[:80]))
        return 3
    is_open, how, since = state_of(name)
    if is_open:
        print(T("busy_open", n=name, since=T("since", s=since) if since else "", how=how))
        return 3
    print("free")
    return 0


def status():
    me = local_state()
    print(f"{device()} ({T('this')}): " + (T("isopen") + T("since", s=me["since"]) if me else T("isclosed")))
    for n in others():
        is_open, how, since = state_of(n)
        print(f"{n}: " + ((T("isopen") + (T("since", s=since) if since else "")) if is_open else T("isclosed")) + f" ({how})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["start"]:
        sys.exit(start())
    elif a == ["stop"]:
        sys.exit(stop())
    elif a == ["status"]:
        status()
    elif a == ["local"]:
        print(json.dumps({"device": device(), "open": bool(local_state()), **(local_state() or {})}))
    elif a == ["heartbeat"]:
        heartbeat()
    elif a[:1] == ["guard"] and len(a) == 2:
        sys.exit(guard(a[1]))
    elif a[:1] == ["close"] and len(a) == 2:
        sys.exit(close(a[1]))
    else:
        print(__doc__)
