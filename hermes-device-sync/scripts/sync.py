"""One sync round. The cron job runs this every 15 minutes (through the bootstrap
$HERMES_HOME/scripts/hermes-sync.sh), and the `hermes` shell wrapper runs it before and after a chat.

  1. commit local changes in the sync repo, pull (rebase), 2. merge memory and your own skills,
  3. check/align the AI setup of this device, 4. start queued requests for this device,
  5. export the newest conversation, 6. commit and push.
Prints nothing when all is well (lines start with "hermes-sync:" otherwise). Uses no model tokens.
"""
import os, subprocess, sys, time, traceback
from pathlib import Path

sys.dont_write_bytecode = True
from common import HH, repo_dir, data_dir, device, git, out

LOCK = HH / "cache" / "hermes-sync.lock"


def commit_all():
    git("add", "-A")
    if subprocess.run(["git", "-C", str(repo_dir()), "diff", "--cached", "--quiet"]).returncode == 0:
        return  # nothing to commit
    git("commit", "-q", "-m", "hermes-sync %s %s" % (device(), time.strftime("%Y-%m-%d %H:%M")))


def step(name, fn):
    try:
        fn()
    except Exception as e:  # one broken step must not stop the others
        out(f"{name} failed on {device()}: {e}")
        if os.environ.get("HERMES_SYNC_DEBUG"):
            traceback.print_exc()


def pull():
    """git pull --rebase. If a conflict touches ONLY files of the sync folder, the remote version wins
    for those hunks (safe: memory is re-merged from this device's own copy right after, and each device
    only writes its own devices/<name>.json). Conflicts in other files of the repo are left to the user."""
    git("fetch", "-q", "origin")
    if subprocess.run(["git", "-C", str(repo_dir()), "rebase", "-q", "--autostash", "@{u}"],
                      capture_output=True).returncode == 0:
        return
    prefix = data_dir().resolve().relative_to(repo_dir().resolve()).as_posix() + "/"
    env = dict(os.environ, GIT_EDITOR="true")
    rb = Path(git("rev-parse", "--git-path", "rebase-merge"))
    rb = rb if rb.is_absolute() else repo_dir() / rb
    run = lambda *a: subprocess.run(["git", "-C", str(repo_dir()), *a], env=env, capture_output=True).returncode
    for _ in range(100):
        if not rb.exists():
            break
        files = git("diff", "--name-only", "--diff-filter=U", check=False).splitlines()
        if any(not f.startswith(prefix) for f in files):
            git("rebase", "--abort", check=False)
            raise RuntimeError("conflict in files outside the sync folder: " + ", ".join(files))
        if files:
            git("checkout", "--ours", "--", *files)  # during a rebase "ours" = the remote side
            git("add", "--", *files)
        if run("rebase", "--continue") and not git("diff", "--name-only", "--diff-filter=U", check=False):
            run("rebase", "--skip")  # the commit became empty after taking the remote version
    if rb.exists():
        git("rebase", "--abort", check=False)
        raise RuntimeError("could not finish the rebase")
    out("resolved a sync conflict automatically (remote version kept for the sync folder)")


def main():
    if not repo_dir().exists():
        out(f"sync repo not found at {repo_dir()} (see {HH / 'hermes-sync.json'})")
        return 1
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        if time.time() - LOCK.stat().st_mtime < 600:
            return 0  # another sync is running
    except OSError:
        pass
    LOCK.write_text(str(os.getpid()))
    try:
        commit_all()
        try:
            pull()
        except RuntimeError as e:
            out(f"pull failed on {device()} (conflict or network): {e}")
            return 1
        import memory_sync, device_check, jobs, handoff, skills_sync
        step("memory sync", memory_sync.run)
        step("skills sync", lambda: [out(m) for m in skills_sync.run(
            HH / "skills", data_dir() / "skills", HH / "cache" / "hermes-sync-skills-base.json", device())])
        step("device check", device_check.run)
        step("request queue", jobs.process)
        step("conversation export", handoff.export)
        step("activity log", handoff.activity)
        commit_all()
        if git("log", "@{u}..HEAD", "--oneline", check=False):
            try:
                git("push", "-q")
            except RuntimeError as e:
                out(f"push failed on {device()}: {e}")
                return 1
        return 0
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
