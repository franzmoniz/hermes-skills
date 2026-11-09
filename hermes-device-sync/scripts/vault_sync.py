"""vault_sync: the Hermes credential vault (`hermes vault`) identical on every device. OPT-IN.

Enabled with "vault_sync": true in <data dir>/config.json (ask the user first).
What goes to the private repo: <data dir>/vault/vault.json.enc = the vault items ENCRYPTED with the
vault key (Fernet, the same encryption Hermes uses). The key ($HERMES_HOME/vault/vault.key) NEVER goes
to the repo: it is copied once from device to device over SSH or by hand (--adopt-key). Without the key
the file is unreadable.

Merges item by item (items have unique ids and are never edited, only added/removed):
- an item added on one device appears on the others;
- an item removed on one device is removed on the others (tombstones, inside the encrypted file);
- never removes an item this device has not synced before (safe on the first run).
Local state: $HERMES_HOME/cache/vault-sync-state.json (ids only, never secrets).

Usage:  python vault_sync.py                         (run by sync.py when enabled)
        python vault_sync.py --adopt-key <key file>  (switch this device to the shared key; re-encrypts)
Tests:  --vault-dir / --shared / --state point at fake folders.
"""
import argparse, datetime as dt, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HH, data_dir, out as _out


def venv_python():
    for f in sorted(HH.glob("installs/*/facts.json")):
        try:
            env = json.loads(f.read_text(encoding="utf-8"))["packages"]["venv"]["environment"]
        except (OSError, ValueError, KeyError):
            continue
        for p in (Path(env) / "Scripts" / "python.exe", Path(env) / "bin" / "python",
                  Path(env) / "venv" / "Scripts" / "python.exe", Path(env) / "venv" / "bin" / "python"):
            if p.exists():
                return str(p)
    return None


try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # this Python lacks cryptography: re-run with the Hermes venv Python
    py = venv_python()
    if not py or os.environ.get("VAULT_SYNC_REEXEC"):
        _out("vault sync: no Python with 'cryptography' found (is Hermes installed?)")
        sys.exit(0)
    sys.exit(subprocess.run([py, __file__, *sys.argv[1:]], env=dict(os.environ, VAULT_SYNC_REEXEC="1"),
                            creationflags=0x08000000 if os.name == "nt" else 0).returncode)

sys.path.insert(0, str(HH / "hermes-agent"))
from agent.vault_store import VaultStore  # same lock / atomic write as Hermes itself


def out(msg):
    _out("vault sync: " + msg)


def kid(key: bytes) -> str:
    return hashlib.sha256(key.strip()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-dir")
    ap.add_argument("--shared")
    ap.add_argument("--state")
    ap.add_argument("--adopt-key")
    a = ap.parse_args()
    vdir = Path(a.vault_dir) if a.vault_dir else HH / "vault"
    shared = Path(a.shared) if a.shared else data_dir() / "vault" / "vault.json.enc"
    state_f = Path(a.state) if a.state else HH / "cache" / "vault-sync-state.json"
    store = VaultStore(base_dir=vdir)
    keyf = vdir / "vault.key"

    with store._locked():
        if a.adopt_key:
            new = Path(a.adopt_key).read_bytes().strip()
            Fernet(new)  # validates the key
            items = store._read_all()  # with the old key
            if keyf.exists() and keyf.read_bytes().strip() != new:
                shutil.copy2(keyf, keyf.with_name("vault.key.bak-" + time.strftime("%Y%m%d%H%M")))
                shutil.copy2(vdir / "vault.json.enc", vdir / ("vault.json.enc.bak-" + time.strftime("%Y%m%d%H%M")))
                keyf.write_bytes(new)
                store._write_all(items)
                out(f"shared key adopted ({len(items)} items re-encrypted; backup of the old key next to it)")
        if not keyf.exists() and not shared.exists():
            return  # no vault here and nothing shared: nothing to do
        local = store._read_all()
        key = keyf.read_bytes().strip()
        f = Fernet(key)
        sh = {"version": 1, "items": [], "deleted": {}}
        if shared.exists() and shared.stat().st_size:
            try:
                sh = json.loads(f.decrypt(shared.read_bytes()).decode("utf-8"))
            except InvalidToken:
                kf = shared.with_name("key-id.txt")
                other = kf.read_text().strip() if kf.exists() else "?"
                out(f"the shared vault uses another key (shared {other}, this device {kid(key)}). Nothing changed. "
                    "Copy vault.key from a device that already syncs (SSH or by hand, NEVER through the repo) "
                    "and run: python vault_sync.py --adopt-key <file>")
                return
        try:
            seen = set(json.loads(state_f.read_text(encoding="utf-8")).get("ids", []))
        except (OSError, ValueError):
            seen = set()
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        deleted = dict(sh.get("deleted") or {})
        loc = {r["id"]: r for r in local if r.get("id")}
        rem = {r["id"]: r for r in sh.get("items") or [] if r.get("id")}
        # removed here since the last sync -> remove everywhere
        for i in seen - set(loc):
            deleted.setdefault(i, now)
        merged = {}
        for i, r in {**rem, **loc}.items():
            if i in deleted:
                continue
            if i in rem and i not in loc and i in seen:
                deleted.setdefault(i, now)  # was here and was removed here
                continue
            merged[i] = r
        new_local = sorted(merged.values(), key=lambda r: (r.get("created_at", ""), r["id"]))
        added = [r["label"] for i, r in merged.items() if i not in loc]
        removed = [r.get("label", i) for i, r in loc.items() if i not in merged]
        if added or removed:
            shutil.copy2(vdir / "vault.json.enc", vdir / "vault.json.enc.bak-sync") if (vdir / "vault.json.enc").exists() else None
            store._write_all(new_local)
            out("vault updated from the other devices: "
                + ", ".join([f"+{x}" for x in added] + [f"-{x}" for x in removed]))
        # shared file: rewrite only when it changed (every Fernet encryption gives different bytes)
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)).isoformat()
        deleted = {i: t for i, t in deleted.items() if t >= cutoff}
        new_sh = {"version": 1, "items": new_local, "deleted": deleted}
        if json.dumps(new_sh, sort_keys=True) != json.dumps(sh, sort_keys=True):
            shared.parent.mkdir(parents=True, exist_ok=True)
            tmp = shared.with_suffix(".tmp")
            tmp.write_bytes(f.encrypt(json.dumps(new_sh).encode("utf-8")))
            os.replace(tmp, shared)
            shared.with_name("key-id.txt").write_text(kid(key) + "\n")
        state_f.parent.mkdir(parents=True, exist_ok=True)
        state_f.write_text(json.dumps({"ids": sorted(merged)}), encoding="utf-8")


def run():
    """Called by sync.py: only when "vault_sync" is true in config.json."""
    from common import shared_cfg
    if not shared_cfg().get("vault_sync"):
        return
    r = subprocess.run([sys.executable, __file__], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       creationflags=0x08000000 if os.name == "nt" else 0)
    for line in (r.stdout + r.stderr).splitlines():
        if line.strip():
            print(line)


if __name__ == "__main__":
    main()
