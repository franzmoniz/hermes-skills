"""Checks that all devices have the same AI setup, and applies the shared fallback chain.

Every device writes <data dir>/devices/<device>.json with NAMES ONLY (never keys or tokens):
providers with credentials, primary model, fallback chain, OS, and how to reach it over SSH.
Then it compares itself with every other device and prints a warning for each difference.

If config.json has "fallback_providers" (a list), it is applied to this device with
`hermes config set` (a backup of config.yaml is made first). So changing the chain once in
the repo changes it on every device, even devices you are away from.
"""
import getpass, json, os, platform, re, shutil, socket, subprocess, sys, time
from pathlib import Path
from common import HH, data_dir, device, shared_cfg, hermes, read_json, write_json, out, strip_ansi

CACHE = HH / "cache" / "hermes-sync-device.json"


def _signature():
    sig = []
    for f in ("config.yaml", "auth.json", ".env"):
        try:
            sig.append(os.path.getmtime(HH / f))
        except OSError:
            sig.append(0)
    return sig


def _collect_ai():
    """providers / model / fallback, using the Hermes CLI (cached until config/auth files change)."""
    cache = read_json(CACHE, {})
    if cache.get("sig") == _signature() and cache.get("ai"):
        return cache["ai"]
    rc, txt = hermes("auth", "list")
    providers = sorted(set(re.findall(r"^(\S+) \(\d+ credentials?\):", strip_ansi(txt), re.M)))
    _, model = hermes("config", "get", "model.default")
    _, mprov = hermes("config", "get", "model.provider")
    _, fb = hermes("config", "get", "fallback_providers", "--json")
    try:
        fallback = [f"{x['provider']}/{x['model']}" for x in (json.loads(strip_ansi(fb).strip().splitlines()[-1]) or [])]
    except (ValueError, IndexError, KeyError, TypeError):
        fallback = []
    last = lambda s: (strip_ansi(s).strip().splitlines() or [""])[-1].strip()
    ai = {"providers": providers, "model": last(model), "model_provider": last(mprov), "fallback": fallback}
    if rc == 0:
        write_json(CACHE, {"sig": _signature(), "ai": ai})
    return ai


def _env_names():
    """Names (never values) of the variables in $HERMES_HOME/.env and $HERMES_HOME/*.env."""
    names = set()
    for f in [HH / ".env", *HH.glob("*.env")]:
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\S", line)
                if m:
                    names.add(m.group(1))
        except OSError:
            pass
    return sorted(names)


def _hermes_pythons():
    """Python interpreters that can run Hermes skill scripts: the Hermes venv first (it has the Google
    libraries), then this one. The plain bundled Python lacks them and would report false 'expired'."""
    import glob
    cands = []
    for f in glob.glob(str(HH / "installs" / "*" / "facts.json")):
        try:
            env = json.load(open(f, encoding="utf-8"))["packages"]["venv"]["environment"]
        except Exception:
            continue
        for exe in (Path(env) / "Scripts" / "python.exe", Path(env) / "bin" / "python3", Path(env) / "bin" / "python"):
            if exe.exists():
                cands.append(str(exe))
    cands.append(sys.executable)
    return cands


def _google_check(gs, home):
    """'ok' | 'expired' | '?' (could not run the check: never reported as expired)."""
    for py in _hermes_pythons():
        try:
            r = subprocess.run([py, str(gs), "--check"], capture_output=True, text=True, timeout=60,
                               env=dict(os.environ, HERMES_HOME=str(home)), stdin=subprocess.DEVNULL,
                               creationflags=0x08000000 if os.name == "nt" else 0)
        except Exception:
            continue
        first = (r.stdout.strip().splitlines() or [""])[0]
        if first.startswith("AUTHENTICATED"):
            return "ok"
        if re.search(r"TOKEN_REVOKED|invalid_grant|NOT_AUTHENTICATED|expired|revoked", r.stdout + r.stderr, re.I):
            return "expired"
    return "?"


def _google_accounts():
    """Google Workspace logins (google-workspace skill): {alias: "ok" | "expired" | "missing"}.
    The default account is alias "default"; extra ones live in $HERMES_HOME/google-accounts/<alias>/.
    Checked with the skill's own `setup.py --check` (no model tokens), at most every 6 hours."""
    gsetup = next(iter(sorted((HH / "skills").glob("*/google-workspace/scripts/setup.py"))), None)
    homes = {}
    if (HH / "google_token.json").exists() or (HH / "google_client_secret.json").exists():
        homes["default"] = HH
    for d in sorted((HH / "google-accounts").glob("*/")) if (HH / "google-accounts").exists() else []:
        homes[d.name] = d
    if not homes:
        return {}
    cache_f = HH / "cache" / "hermes-sync-google.json"
    cache = read_json(cache_f, {})
    if cache.get("at", 0) > time.time() - 6 * 3600 and set(cache.get("acc", {})) == set(homes):
        return cache["acc"]
    acc = {}
    for alias, home in homes.items():
        if not (home / "google_token.json").exists():
            acc[alias] = "missing"
            continue
        if not gsetup:
            acc[alias] = "ok"
            continue
        if True:
            acc[alias] = _google_check(gsetup, home)
    write_json(cache_f, {"at": time.time(), "acc": acc})
    return acc


def _mcp_servers():
    _, txt = hermes("config", "get", "mcp_servers", "--json")
    try:
        d = json.loads((strip_ansi(txt).strip().splitlines() or ["{}"])[-1]) or {}
        return sorted(d.keys()) if isinstance(d, dict) else []
    except ValueError:
        return []


def _collect_access():
    """Everything this device is logged in to / connected with - NAMES ONLY, never secrets."""
    return {"env_names": _env_names(), "google": _google_accounts(), "mcp_servers": _mcp_servers()}


def _apply_fallback(want, have):
    names = [f"{w['provider']}/{w['model']}" for w in want]
    if names == have:
        return False
    cfg = HH / "config.yaml"
    if cfg.exists():
        shutil.copy2(cfg, cfg.with_name("config.yaml.bak-" + time.strftime("%Y%m%d%H%M")))
    keep = ("provider", "model", "base_url")  # base_url: local/custom endpoints (e.g. Ollama); never keys
    rc, txt = hermes("config", "set", "fallback_providers",
                     json.dumps([{k: w[k] for k in keep if w.get(k)} for w in want]))
    if rc:
        out("could not apply the shared fallback chain: " + strip_ansi(txt)[-200:])
        return False
    out(f"fallback chain of {device()} updated from config.json: " + " -> ".join(names))
    return True


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip if not ip.startswith(("127.", "100.")) else None
    except OSError:
        return None


def _tailscale_ip():
    exe = shutil.which("tailscale")
    if not exe and os.name == "nt" and os.path.exists(r"C:\Program Files\Tailscale\tailscale.exe"):
        exe = r"C:\Program Files\Tailscale\tailscale.exe"
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=10)
        ip = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else None
        return ip
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def _ssh_server():
    try:
        with socket.create_connection(("127.0.0.1", 22), timeout=1):
            return True
    except OSError:
        return False


def _reach():
    pub = Path.home() / ".ssh" / "hermes_sync.pub"
    bash = None
    if os.name == "nt":
        git_exe = shutil.which("git")
        cands = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
                 *sorted((HH / "tools").glob("git-*/usr/bin/bash.exe"))]
        if git_exe:  # <git>/cmd/git.exe -> <git>/bin/bash.exe or <git>/usr/bin/bash.exe
            root = Path(git_exe).resolve().parent.parent
            cands += [root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"]
        for c in cands:
            if c.exists():
                bash = str(c)
                break
    return {
        "os": "windows" if os.name == "nt" else platform.system().lower(),
        "user": getpass.getuser(),
        "lan_ip": _lan_ip(),
        "tailscale_ip": _tailscale_ip(),
        "ssh_server": _ssh_server(),
        "ssh_pubkey": pub.read_text(encoding="utf-8").strip() if pub.exists() else None,
        "bash": bash,
        "sync_script": str(HH / "scripts" / "hermes-sync.sh"),
        "python": sys.executable,
        "sync_scripts_dir": str(Path(__file__).resolve().parent),
    }


def _check_local_models(want):
    """Warn if a fallback entry points at a LOCAL endpoint (offline model) that is not ready here."""
    import urllib.request
    for w in want or []:
        url = (w.get("base_url") or "").rstrip("/")
        if not re.match(r"https?://(localhost|127\.0\.0\.1|\[::1\])[:/]", url + "/"):
            continue
        try:
            with urllib.request.urlopen(url + "/models", timeout=3) as r:
                ids = [m.get("id", "") for m in json.loads(r.read().decode("utf-8", "replace")).get("data", [])]
        except Exception:
            out(f"local model server {url} is not running on {device()}: offline answers won't work "
                f"(start it, e.g. `ollama serve`, or install it: see 'Optional: answer offline' in SKILL.md)")
            continue
        m = w.get("model", "")
        if m and not any(i == m or i == m + ":latest" for i in ids):
            out(f"local model '{m}' is missing on {device()} (pull a model and alias it: "
                f"`ollama pull <model>` then `ollama cp <model> {m}`)")


def run():
    me = device()
    cfg = shared_cfg()
    ai = _collect_ai()
    want = cfg.get("fallback_providers")
    if isinstance(want, list) and want and _apply_fallback(want, ai["fallback"]):
        CACHE.unlink(missing_ok=True)
        ai = _collect_ai()
    if isinstance(want, list):
        _check_local_models(want)
    access = _collect_access()
    info = {"device": me, **ai, "access": access, **_reach(), "last_seen": time.strftime("%Y-%m-%d")}
    for alias, st in access["google"].items():
        if st != "ok":
            out(f"Google account '{alias}' on {me} is {st}: log in again on THIS device "
                f"(google-workspace skill, HERMES_HOME={HH / 'google-accounts' / alias if alias != 'default' else HH}). "
                f"Copied tokens stop working; every device needs its own login.")
    ddir = data_dir() / "devices"
    write_json(ddir / f"{me}.json", info)

    for f in sorted(ddir.glob("*.json")):
        o = read_json(f, {})
        name = o.get("device") or f.stem
        if name == me:
            continue
        missing = sorted(set(o.get("providers", [])) - set(ai["providers"]))
        if missing:
            out(f"{me} is missing AI accounts that {name} has: {', '.join(missing)} "
                f"(log in here with: hermes auth add <provider>)")
        oa = o.get("access") or {}
        for key, label in (("env_names", "keys/settings in .env files"), ("mcp_servers", "MCP servers")):
            miss = sorted(set(oa.get(key, [])) - set(access[key]))
            if miss:
                out(f"{me} is missing {label} that {name} has: {', '.join(miss)}")
        miss = sorted(a for a, st in (oa.get("google") or {}).items() if st == "ok" and access["google"].get(a) != "ok")
        if miss:
            out(f"{me} is missing Google logins that {name} has: {', '.join(miss)}")
        if o.get("model") and o.get("model") != ai["model"]:
            out(f"different primary model: {me}={ai['model'] or '?'} vs {name}={o['model']}")
        if o.get("fallback") != ai["fallback"]:
            out(f"different fallback chain between {me} and {name} "
                f"({' -> '.join(ai['fallback']) or 'none'} vs {' -> '.join(o.get('fallback') or []) or 'none'})")


if __name__ == "__main__":
    run()
