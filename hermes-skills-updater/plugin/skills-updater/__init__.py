"""skills-updater: on the FIRST prompt of every session, before anything else, Hermes tells you which of
your Hermes's Skills (github.com/franzmoniz/hermes-skills) have an update, what changed, and asks whether
to update. Updates you already accepted on another device (Hermes Device Sync) are applied silently.
The check is cached for 6 hours and gives up after a few seconds when offline (never blocks Hermes)."""
from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

logger = logging.getLogger("skills-updater")
_asked: set[str] = set()


def _updater():
    hh = Path(os.environ.get("HERMES_HOME") or (Path(os.environ["LOCALAPPDATA"]) / "hermes"
              if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".hermes"))
    for p in [hh / "scripts" / "hermes-skills-updater.py", *(hh / "skills").rglob("hermes-skills-updater/scripts/updater.py")]:
        if p.exists():
            spec = importlib.util.spec_from_file_location("hermes_skills_updater", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, p
    return None, None


def _on_pre_llm_call(session_id=None, is_first_turn=False, **_):
    if not is_first_turn or session_id in _asked:
        return None
    _asked.add(session_id)
    try:
        upd, path = _updater()
        if upd is None:
            return None
        auto_done, ask = upd.run_startup()
    except Exception as exc:
        logger.debug("skills-updater skipped: %s", exc)
        return None
    if not auto_done and not ask:
        return None
    lines = ["[skills-updater plugin] BEFORE answering the user's message, do this first:"]
    for u in auto_done:
        lines.append(f"- Tell the user: the skill {u['skill']} was updated to {u['latest']} automatically "
                     f"(they accepted this update on {u['accepted_on']}).")
    if ask:
        lines.append("- Tell the user that these skills from github.com/franzmoniz/hermes-skills have updates. "
                     "For each one, summarise the changelog below in plain words, grouped as added / changed or "
                     "improved / fixed / removed, and ask whether they want to update it now (one yes/no per skill). "
                     "Then wait for the answer before doing anything else, unless the user's message is urgent: "
                     "then answer it and ask about the updates at the end.")
        for u in ask:
            lines.append(f"\n## {u['skill']}: {u['installed']} -> {u['latest']}\n{u['changelog']}")
        lines.append(f"\n- If the user says yes for a skill: run `python \"{path}\" apply <skill>` with the terminal "
                     f"tool and report its output. If no: run `python \"{path}\" decline <skill> <version>` "
                     "(they are asked again only when a newer version comes out). With Hermes Device Sync, the "
                     "answer is shared with their other devices.")
    return {"context": "\n".join(lines)}


def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
