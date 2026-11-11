"""Saves everything right after EACH Hermes answer (Hermes shell hook `post_llm_call`), so the user can
close the terminal at any moment (even Alt+F4) and nothing is lost: the conversation, the activity log
and the memory reach the other devices seconds after the answer, without waiting for the 15-min job.

  turn_sync.py            (called by the hook) starts the work in the background and returns at once,
                          so the answer is never delayed
  turn_sync.py --child    (internal) waits for the answer to be stored, refreshes the Hermes's Terminal recap (if that skill is installed)
                          and the activity-log line, then runs one sync. If more answers arrive
                          meanwhile, it loops until everything is saved. No model tokens unless the
                          Hermes's Terminal recap is enabled.
"""
import os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HH  # noqa: E402

CACHE = HH / "cache"
LOCK, PENDING = CACHE / "hermes-sync-turn.lock", CACHE / "hermes-sync-turn.pending"
NOWIN = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: no console windows popping up


def spawn():
    try:
        sys.stdin.read()
    except Exception:
        pass
    CACHE.mkdir(parents=True, exist_ok=True)
    PENDING.touch()
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                     creationflags=(NOWIN | 0x00000200) if os.name == "nt" else 0,  # + NEW_PROCESS_GROUP
                     start_new_session=(os.name != "nt"))


def child():
    try:
        if time.time() - LOCK.stat().st_mtime < 600:
            return  # another run is active; it sees PENDING and loops
    except OSError:
        pass
    LOCK.write_text(str(os.getpid()))
    try:
        import handoff, sync
        for _ in range(20):
            if not PENDING.exists():
                break
            PENDING.unlink(missing_ok=True)
            time.sleep(6)  # let Hermes store the final answer
            LOCK.touch()
            term = handoff.terminal()  # Hermes's Terminal installed: refresh its recap first
            for fn in ((lambda: term.summarize(term.current())) if term else None, handoff.activity):
                try:
                    fn and fn()
                except Exception:
                    pass
            sync.main()
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    child() if sys.argv[1:] == ["--child"] else spawn()
