"""Installs Hermes's Terminal on this device (idempotent: safe to run again; also run by post_update).

  python setup.py [--title "Hermes's Terminal"] [--recap-provider <p> --recap-model <m>] [--language English]
                  [--no-recap]

1. writes $HERMES_HOME/hermes-terminal.json (title + recap settings; existing values are kept unless given)
2. adds to your shell profile (PowerShell on Windows, bash/zsh elsewhere; a backup is made first):
   - the shared `hermes` launcher (same code in every Hermes's Skill that plugs into `hermes`)
   - this skill's step: open "Hermes's Terminal" with its recap, write the recap when Hermes closes
The first time you type `hermes`, your newest conversation becomes "Hermes's Terminal" and is pinned.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from terminal import HH, CFG, rj, wj  # noqa: E402

BLOCKS = {"launcher": ("# >>> hermes-launcher >>>", "# <<< hermes-launcher <<<"),
          "terminal": ("# >>> hermes-terminal >>>", "# <<< hermes-terminal <<<")}


def say(m):
    print("hermes-terminal setup: " + m)


def replace_block(path, name, body):
    begin, end = BLOCKS[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    block = f"{begin}\n{body.strip()}\n{end}"
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\r?\n?", re.S)
    if pat.search(cur) and pat.search(cur).group(0).strip() == block.strip():
        return False
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak-" + time.strftime("%Y%m%d%H%M")))
    if pat.search(cur):
        new = pat.sub(lambda _: block + "\n", cur, count=1)
    else:
        new = (cur.rstrip() + "\n\n" if cur.strip() else "") + block + "\n"
    path.write_text(new, encoding="utf-8")
    return True


def profiles():
    if os.name == "nt":
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('MyDocuments')"],
                           capture_output=True, text=True)
        docs = Path(r.stdout.strip() or Path.home() / "Documents")
        t = [docs / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"]
        if shutil.which("pwsh") or (docs / "PowerShell").exists():
            t.append(docs / "PowerShell" / "Microsoft.PowerShell_profile.ps1")
        return t
    return [p for p in (Path.home() / ".bashrc", Path.home() / ".zshrc") if p.exists()] or [Path.home() / ".bashrc"]


def old_sync_wrapper(text):
    """Hermes Device Sync before 0.7.0 had its own `hermes` function that would fight with this one."""
    m = re.search(r"# >>> hermes-device-sync >>>(.*?)# <<< hermes-device-sync <<<", text, re.S)
    return bool(m and ("function hermes" in m.group(1) or "\nhermes()" in m.group(1)))


def install_shell():
    ext = "ps1" if os.name == "nt" else "sh"
    launcher = (PKG / "templates" / f"launcher.{ext}").read_text(encoding="utf-8")
    mine = (PKG / "templates" / f"terminal.{ext}").read_text(encoding="utf-8")
    mine = mine.replace("__SCRIPT__", str(PKG / "scripts" / "terminal.py")).replace("__PYTHON__", sys.executable)
    if os.name == "nt":
        mine = "if (-not $global:HermesHooks) { $global:HermesHooks = @{} }\n" + mine
    for p in profiles():
        if p.exists() and old_sync_wrapper(p.read_text(encoding="utf-8-sig")):
            say("WARNING: Hermes Device Sync older than 0.7.0 is installed in " + str(p) + ". Update it first "
                "(it then plugs into the same `hermes` launcher); until then the two would conflict.")
            return False
        changed = replace_block(p, "launcher", launcher) | replace_block(p, "terminal", mine)
        say(("updated " if changed else "already up to date: ") + str(p))
    if os.name == "nt":
        pol = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-ExecutionPolicy"], capture_output=True,
                             text=True).stdout.strip()
        if pol in ("Restricted", "AllSigned", "Undefined"):
            say(f"WARNING: PowerShell execution policy is '{pol}', so the profile will NOT load. Ask the user, "
                "then run: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--recap-provider")
    ap.add_argument("--recap-model")
    ap.add_argument("--language")
    ap.add_argument("--no-recap", action="store_true")
    a = ap.parse_args()
    c = rj(CFG, {}) or {}
    if not c:  # first install: take over the recap settings of Hermes Device Sync (older versions had them)
        hs = rj(HH / "hermes-sync.json", {}) or {}
        old = (rj(Path(hs["data_dir"]) / "config.json", {}) or {}).get("summary") if hs.get("data_dir") else None
        if old:
            c["summary"] = old
            say("recap settings taken over from Hermes Device Sync")
    c.setdefault("title", "Hermes's Terminal")
    c.setdefault("summary", {"enabled": False, "provider": None, "model": None, "language": "English"})
    if a.title:
        c["title"] = a.title
    if a.recap_provider:
        c["summary"].update(enabled=True, provider=a.recap_provider, model=a.recap_model or None)
    if a.language:
        c["summary"]["language"] = a.language
    if a.no_recap:
        c["summary"]["enabled"] = False
    c["script"] = str(PKG / "scripts" / "terminal.py")  # other skills (e.g. Device Sync) find it here
    wj(CFG, c)
    say(f"settings: {CFG} (title '{c['title']}', recap {'on: ' + str(c['summary'].get('provider')) if c['summary'].get('enabled') else 'off'})")
    if install_shell() is False:
        return 1
    say("done. Open a NEW terminal and type `hermes`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
