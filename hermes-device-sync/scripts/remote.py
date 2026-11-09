"""Optional remote control between your devices over SSH (home network or Tailscale).

  python remote.py keygen                 create this device's key ~/.ssh/hermes_sync (published by the
                                          next sync in devices/<this device>.json; public part only)
  python remote.py authorize "<device>"   on the TARGET: allow <device>'s key to log in here
  python remote.py check "<device>"       prints "online via <address>" or "offline"
  python remote.py run "<device>" [file]  runs a script on <device> (PowerShell on Windows, bash elsewhere);
                                          the script comes from the file or stdin
  python remote.py sync "<device>"        makes <device> sync now (e.g. to start a queued request at once)

Addresses are read from devices/<device>.json (LAN address first, then Tailscale).
"""
import base64, os, socket, subprocess, sys
from pathlib import Path
from common import data_dir, device, read_json, out

KEY = Path.home() / ".ssh" / "hermes_sync"


def info(name):
    d = read_json(data_dir() / "devices" / f"{name}.json")
    if not d:
        out(f"unknown device '{name}' (no devices/{name}.json yet; run a sync on it first)")
        sys.exit(2)
    return d


def keygen():
    if KEY.exists():
        out(f"key already exists: {KEY}")
        return
    KEY.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", f"hermes-sync {device()}", "-f", str(KEY)],
                   check=True)
    out(f"created {KEY}. Run a sync so the other devices can see the public key.")


def authorize(name):
    pub = info(name).get("ssh_pubkey")
    if not pub:
        out(f"{name} has no key yet: run `remote.py keygen` and a sync on {name} first")
        sys.exit(2)
    if os.name == "nt" and _is_admin_user():
        # Windows OpenSSH ignores ~/.ssh/authorized_keys for administrators
        target = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "ssh" / "administrators_authorized_keys"
        out("this Windows user is an administrator: the key must go to " + str(target) +
            " with restricted permissions. Run templates/windows-ssh-server.ps1 in an elevated PowerShell "
            "with -AuthorizeKey \"" + pub + "\"")
        return
    ak = Path.home() / ".ssh" / "authorized_keys"
    ak.parent.mkdir(parents=True, exist_ok=True)
    cur = ak.read_text(encoding="utf-8") if ak.exists() else ""
    if pub in cur:
        out(f"{name} is already authorized")
        return
    with open(ak, "a", encoding="utf-8", newline="\n") as f:
        f.write(("" if cur.endswith("\n") or not cur else "\n") + pub + "\n")
    if os.name != "nt":
        os.chmod(ak, 0o600)
    out(f"{name} can now log in here over SSH")


def _is_admin_user():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent())"
                        ".Groups -contains (New-Object Security.Principal.SecurityIdentifier 'S-1-5-32-544')"],
                       capture_output=True, text=True)
    return "True" in r.stdout


def address(d):
    for a in (d.get("lan_ip"), d.get("tailscale_ip")):
        if not a:
            continue
        try:
            with socket.create_connection((a, 22), timeout=2 if a == d.get("lan_ip") else 5):
                return a
        except OSError:
            pass
    return None


def run(name, src):
    d = info(name)
    a = address(d)
    if not a:
        out(f"{name} is offline (switched off, nobody logged in, or not on the same network/Tailscale)")
        sys.exit(2)
    ssh = ["ssh", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=8",
           "-o", "StrictHostKeyChecking=accept-new", f"{d['user']}@{a}"]
    if d.get("os") == "windows":
        src = "$ProgressPreference='SilentlyContinue'\n" + src
        enc = base64.b64encode(src.encode("utf-16le")).decode()
        r = subprocess.run(ssh + ["powershell -NoProfile -NonInteractive -EncodedCommand " + enc], stdin=subprocess.DEVNULL)
    else:
        r = subprocess.run(ssh + ["bash -s"], input=src, text=True)
    return r.returncode


def sync(name):
    d = info(name)
    if d.get("os") == "windows":
        bash = d.get("bash") or "bash"
        return run(name, f"& '{bash}' '{d['sync_script']}'")
    return run(name, f"sh '{d['sync_script']}'")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["keygen"]:
        keygen()
    elif a[:1] == ["authorize"] and len(a) == 2:
        authorize(a[1])
    elif a[:1] == ["check"] and len(a) == 2:
        x = address(info(a[1]))
        print(f"online via {x}" if x else "offline")
    elif a[:1] == ["run"] and len(a) in (2, 3):
        sys.exit(run(a[1], open(a[2], encoding="utf-8").read() if len(a) == 3 else sys.stdin.read()))
    elif a[:1] == ["sync"] and len(a) == 2:
        sys.exit(sync(a[1]))
    else:
        print(__doc__)
