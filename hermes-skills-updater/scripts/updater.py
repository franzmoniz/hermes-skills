"""Hermes's Skills updater: checks https://github.com/franzmoniz/hermes-skills for new versions of the
skills you installed from there, shows what changed, and updates only the ones you say yes to.

  python updater.py check            list available updates (JSON on the last line)
  python updater.py prompt           ask in the terminal, one skill at a time (y/n), then apply
  python updater.py apply <skill>    update <skill> now (backup first)
  python updater.py decline <skill> <version>   don't ask again about this version
  python updater.py status           installed skills, versions, decisions

How it decides:
- Installed = a folder under $HERMES_HOME/skills whose SKILL.md `name:` is listed in the repo's
  skills.json and whose author mentions franzmoniz. Its version = VERSION file (or `version:` in SKILL.md).
- Every answer (yes / no for a version) is remembered. With Hermes Device Sync installed, the answer
  is also written to the sync repo (skill-updates.json): your other devices then apply an update you
  accepted WITHOUT asking again, and don't ask about a version you declined.
- After an update (or when the skill's files arrived through the sync), the skill's own
  scripts/post_update.py runs on this device (e.g. to refresh a plugin or the sync scripts).
- Offline or GitHub slow: nothing is asked, Hermes starts normally (checks are cached for 6 hours).
Stdlib only. Never deletes anything without a backup (in $HERMES_HOME/backups/skills-updater/).
"""
import io, json, os, re, shutil, subprocess, sys, time, urllib.request, zipfile
from pathlib import Path

REPO = "franzmoniz/hermes-skills"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
ZIP = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
CACHE_H = 6
TIMEOUT = 4


def hermes_home():
    h = os.environ.get("HERMES_HOME")
    if h:
        return Path(h)
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "hermes"
    return Path.home() / ".hermes"


HH = hermes_home()
STATE = HH / "cache" / "skills-updater.json"


def rj(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return d


def wj(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:3]) or (0,)


def fetch(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-skills-updater", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------ local ---
def frontmatter(md):
    m = re.match(r"^---\s*\n(.*?)\n---", md.replace("\r\n", "\n"), re.S)
    out = {}
    for line in (m.group(1) if m else "").splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def installed(registry):
    found = {}
    for md in (HH / "skills").rglob("SKILL.md"):
        try:
            fm = frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        name = fm.get("name")
        if name in registry and "franzmoniz" in (fm.get("author") or "").lower():
            vf = md.parent / "VERSION"
            ver = vf.read_text(encoding="utf-8").strip() if vf.exists() else fm.get("version", "0")
            found[name] = {"dir": md.parent, "version": ver}
    return found


# ----------------------------------------------------------- sync (opt) ---
def sync_file():
    c = rj(HH / "hermes-sync.json", {}) or {}
    return Path(c["data_dir"]) / "skill-updates.json" if c.get("data_dir") else None


def run_sync():
    c = rj(HH / "hermes-sync.json", {}) or {}
    s = Path(c.get("data_dir", "")) / "scripts" / "sync.py"
    if c.get("data_dir") and s.exists():
        subprocess.run([sys.executable, str(s)], stdin=subprocess.DEVNULL)


def decisions():
    d = {}
    sf = sync_file()
    if sf:
        d.update(rj(sf, {}) or {})
    st = rj(STATE, {}) or {}
    for k, v in (st.get("decisions") or {}).items():
        if vkey(v.get("version")) >= vkey((d.get(k) or {}).get("version")):
            d[k] = v
    return d


def remember(skill, version, decision):
    rec = {"version": version, "decision": decision, "device": device_name(), "at": time.strftime("%Y-%m-%d %H:%M")}
    st = rj(STATE, {}) or {}
    st.setdefault("decisions", {})[skill] = rec
    wj(STATE, st)
    sf = sync_file()
    if sf:
        d = rj(sf, {}) or {}
        d[skill] = rec
        wj(sf, d)


def device_name():
    c = rj(HH / "hermes-sync.json", {}) or {}
    import socket
    return c.get("device") or socket.gethostname()


# ------------------------------------------------------------------ check ---
def changelog_between(skill, old, new):
    try:
        txt = fetch(RAW + f"{skill}/CHANGELOG.md").decode("utf-8", "replace").replace("\r\n", "\n")
    except Exception:
        return "(no changelog available)"
    parts, keep = [], False
    for line in txt.splitlines():
        m = re.match(r"^##\s+\[?v?(\d+\.\d+(?:\.\d+)?)", line)
        if m:
            keep = vkey(old) < vkey(m.group(1)) <= vkey(new)
        if keep:
            parts.append(line)
    return "\n".join(parts).strip() or "(no changelog entry for these versions)"


def check(force=False):
    """[{skill, installed, latest, changelog, auto}] ; auto = accepted on another device -> apply silently."""
    st = rj(STATE, {}) or {}
    cached = st.get("registry")
    if not force and cached and time.time() - st.get("registry_at", 0) < CACHE_H * 3600:
        registry = cached
    else:
        try:
            registry = json.loads(fetch(RAW + "skills.json"))
        except Exception:
            registry = cached or {}
        st = rj(STATE, {}) or {}
        st.update(registry=registry, registry_at=time.time())
        wj(STATE, st)
    dec = decisions()
    out = []
    for name, info in installed(registry).items():
        latest = str((registry.get(name) or {}).get("version") or "0")
        if vkey(latest) <= vkey(info["version"]):
            continue
        d = dec.get(name) or {}
        if d.get("decision") == "no" and vkey(d.get("version")) >= vkey(latest):
            continue  # declined this version (here or on another device)
        auto = d.get("decision") == "yes" and vkey(d.get("version")) >= vkey(latest)
        out.append({"skill": name, "installed": info["version"], "latest": latest, "auto": auto,
                    "accepted_on": d.get("device") if auto else None,
                    "changelog": "" if auto else changelog_between(name, info["version"], latest)})
    return out


# ------------------------------------------------------------------ apply ---
def post_update(skill, sdir, version):
    """Run the skill's own post-update step once per version on this device."""
    st = rj(STATE, {}) or {}
    done = st.setdefault("post_update_done", {})
    if done.get(skill) == version:
        return
    hook = Path(sdir) / "scripts" / "post_update.py"
    if hook.exists():
        r = subprocess.run([sys.executable, str(hook)], cwd=str(sdir), capture_output=True, text=True)
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode:
            print(f"skills-updater: post-update step of {skill} failed: {(r.stderr or '').strip()[-400:]}")
            return
    done[skill] = version
    wj(STATE, st)


def apply(skill, quiet=False):
    registry = (rj(STATE, {}) or {}).get("registry") or json.loads(fetch(RAW + "skills.json"))
    inst = installed(registry).get(skill)
    if not inst:
        print(f"skills-updater: {skill} is not installed here")
        return 2
    data = fetch(ZIP, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(data))
    root = z.namelist()[0].split("/")[0]
    prefix = f"{root}/{skill}/"
    members = [n for n in z.namelist() if n.startswith(prefix) and not n.endswith("/")]
    if not members:
        print(f"skills-updater: {skill} not found in the repository")
        return 2
    sdir = Path(inst["dir"])
    bdir = HH / "backups" / "skills-updater"
    bdir.mkdir(parents=True, exist_ok=True)
    backup = shutil.make_archive(str(bdir / f"{skill}-{inst['version']}-{time.strftime('%Y%m%d%H%M%S')}"), "zip", sdir)
    for n in members:
        dest = sdir / n[len(prefix):]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(n))
    new = (sdir / "VERSION").read_text(encoding="utf-8").strip() if (sdir / "VERSION").exists() else \
        frontmatter((sdir / "SKILL.md").read_text(encoding="utf-8")).get("version", "?")
    remember(skill, new, "yes")
    post_update(skill, sdir, new)
    if not quiet:
        print(f"skills-updater: {skill} updated {inst['version']} -> {new} (backup: {backup})")
    run_sync()
    return 0


def decline(skill, version):
    remember(skill, version, "no")
    run_sync()
    print(f"skills-updater: OK, not updating {skill} to {version}. You will be asked again on the next version.")


def catch_up():
    """Skill files that arrived through the sync (or an older update) still need their post-update here."""
    registry = (rj(STATE, {}) or {}).get("registry") or {}
    for name, info in installed(registry).items():
        post_update(name, info["dir"], info["version"])


def run_startup():
    """For the plugin / wrapper: auto-apply updates accepted on another device; return what to ask about."""
    try:
        ups = check()
    except Exception:
        return [], []
    auto_done, ask = [], []
    for u in ups:
        if u["auto"]:
            try:
                if apply(u["skill"], quiet=True) == 0:
                    auto_done.append(u)
            except Exception:
                pass
        else:
            ask.append(u)
    try:
        catch_up()
    except Exception:
        pass
    return auto_done, ask


def prompt():
    auto_done, ask = run_startup()
    for u in auto_done:
        print(f"skills-updater: {u['skill']} updated to {u['latest']} (you accepted it on {u['accepted_on']}).")
    for u in ask:
        print(f"\n=== Update available: {u['skill']} {u['installed']} -> {u['latest']} ===\n{u['changelog']}\n")
        try:
            a = input(f"Update {u['skill']} now? [y/n] ").strip().lower()
        except EOFError:
            return 0
        if a in ("y", "yes", "s", "sim"):
            apply(u["skill"])
        elif a in ("n", "no", "nao", "não"):
            decline(u["skill"], u["latest"])
    return 0


def status():
    check(force=True)
    registry = (rj(STATE, {}) or {}).get("registry") or {}
    dec = decisions()
    for name, info in installed(registry).items():
        d = dec.get(name) or {}
        print(f"{name}: installed {info['version']}, latest {(registry.get(name) or {}).get('version', '?')}"
              + (f", last answer: {d.get('decision')} for {d.get('version')} on {d.get('device')}" if d else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["check"]:
        print(json.dumps(check(force=True), ensure_ascii=False))
    elif a == ["prompt"]:
        sys.exit(prompt())
    elif a[:1] == ["apply"] and len(a) == 2:
        sys.exit(apply(a[1]))
    elif a[:1] == ["decline"] and len(a) == 3:
        decline(a[1], a[2])
    elif a == ["status"]:
        status()
    else:
        print(__doc__)
