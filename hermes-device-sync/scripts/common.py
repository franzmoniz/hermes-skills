"""Shared helpers for hermes-device-sync (stdlib only, works on Windows, Linux, macOS, Termux).

Layout:
  <repo>/<sync dir>/            data dir inside your private sync repo (default "hermes-sync")
      scripts/                  these scripts (every device runs the copy from the repo)
      config.json               shared settings for all devices
      memory/                   MEMORY.md / USER.md merged across devices
      devices/<name>.json       what each device has (no secrets)
      queue/                    requests left for another device
  $HERMES_HOME/hermes-sync.json local settings of this device: {"repo", "data_dir", "device"}
  $HERMES_HOME/scripts/hermes-sync.sh   tiny bootstrap the cron job runs
"""
import json, os, re, shutil, socket, subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def hermes_home():
    h = os.environ.get("HERMES_HOME")
    if h:
        return Path(h)
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "hermes"
    return Path.home() / ".hermes"


HH = hermes_home()
LOCAL_CFG = HH / "hermes-sync.json"


def local_cfg():
    try:
        return json.loads(LOCAL_CFG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def data_dir():
    c = local_cfg()
    return Path(c["data_dir"]) if c.get("data_dir") else SCRIPTS.parent


def repo_dir():
    c = local_cfg()
    if c.get("repo"):
        return Path(c["repo"])
    r = subprocess.run(["git", "-C", str(SCRIPTS), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else SCRIPTS.parent.parent


def device():
    return local_cfg().get("device") or socket.gethostname()


DEFAULT_CONFIG = {
    "sessions_branch": "hermes-sessions",
    "fallback_providers": None,          # list of {"provider","model"} applied on every device; null = don't manage
    "summary": {"enabled": False, "provider": None, "model": None, "language": "English"},
    "queue": {"rules": "", "max_hours": 3},
}


def shared_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        user = json.loads((data_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        user = {}
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def hermes_bin():
    for c in (HH / "bin" / "hermes.exe", HH / "bin" / "hermes"):
        if c.exists():
            return str(c)
    return shutil.which("hermes") or "hermes"


def hermes(*args, timeout=120):
    """Runs the Hermes CLI. Returns (returncode, stdout)."""
    try:
        r = subprocess.run([hermes_bin(), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def git(*args, check=True, env=None, cwd=None):
    r = subprocess.run(["git", "-C", str(cwd or repo_dir()), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    if check and r.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), (r.stderr or r.stdout).strip()))
    return r.stdout.strip()


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def strip_ansi(s):
    return ANSI.sub("", s or "")


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    new = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    try:
        if p.read_text(encoding="utf-8") == new:
            return False
    except OSError:
        pass
    p.write_text(new, encoding="utf-8", newline="\n")
    return True


def out(msg):
    """Everything this tool prints starts with 'hermes-sync:' so it is easy to spot in cron output."""
    print("hermes-sync: " + msg)
    sys.stdout.flush()
