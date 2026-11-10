"""model-return: always climb back to the best AI model that works, but never override a manual choice.

What it does, at the start of every prompt (turn):

1. AUTOMATIC FALLBACK (Hermes moved you to a fallback because a model failed):
   Hermes alone only retries the primary when its rate-limit cooldown ends (can be up to 4 h),
   and never climbs to a better fallback. This plugin, on every prompt while you are NOT on the
   primary, sends a tiny test request to the primary and to every fallback ABOVE the current one.
   The first one that answers wins: Hermes switches to it for this prompt.

2. MANUAL CHOICE (you switched with /model):
   Hermes treats your choice as the session's new primary, so nothing is ever switched for you.
   Every 5th prompt the reply ends with a short note:
   - if your chosen model is one of your fallbacks: which better models are available right now;
   - if it is not a fallback: a question, keep this model or go back to the primary
     (or to the best fallback that is available right now).

It hooks into Hermes by wrapping ``agent.agent_runtime_helpers.restore_primary_runtime`` (Hermes calls
it at the start of every turn) and adds a ``pre_llm_call`` hook for the every-5-prompts note.
Every step is wrapped in try/except: if anything goes wrong, Hermes behaves exactly as without it.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import threading
import time

logger = logging.getLogger("model-return")

EVERY_N_PROMPTS = 5
PROBE_TIMEOUT_S = 8.0
_ORIG = None
_notes: dict[str, str] = {}  # session_id -> note for this prompt's reply
_lock = threading.Lock()


# ---------------------------------------------------------------- config ---
def _config_routes():
    """[(provider, model, base_url)] = configured primary first, then fallback_providers in order."""
    from hermes_cli.config import load_config, cfg_get
    cfg = load_config()
    m = cfg_get(cfg, "model", default={}) or {}
    if isinstance(m, str):
        m = {"default": m}
    primary = ((m.get("provider") or "").strip().lower(), (m.get("default") or m.get("model") or "").strip(),
               (m.get("base_url") or "").strip())
    chain = []
    for e in cfg_get(cfg, "fallback_providers", default=[]) or []:
        if isinstance(e, dict) and e.get("provider") and e.get("model"):
            chain.append((e["provider"].strip().lower(), e["model"].strip(), (e.get("base_url") or "").strip()))
    return primary, chain


def _same(a_prov, a_model, b_prov, b_model) -> bool:
    return (a_prov or "").lower() == (b_prov or "").lower() and \
        (a_model or "").lower().split("/")[-1] == (b_model or "").lower().split("/")[-1]


def _label(route) -> str:
    return f"{route[1]} ({route[0]})"


# ----------------------------------------------------------------- probe ---
def _probe(route) -> bool:
    """One tiny request (1 output token). True only when the model really answers."""
    provider, model, base_url = route
    try:
        if provider in ("custom", "ollama", "lmstudio", "vllm", "llamacpp") and base_url:
            # Local/OpenAI-compatible server (e.g. Ollama): talk to it directly, no key needed.
            from openai import OpenAI
            OpenAI(base_url=base_url, api_key="local", timeout=PROBE_TIMEOUT_S, max_retries=0).chat.completions.create(
                model=model, messages=[{"role": "user", "content": "ping"}], max_tokens=1)
            return True
        from agent.auxiliary_client import resolve_provider_client
        client, resolved = resolve_provider_client(provider, model, explicit_base_url=base_url or None)
        if client is None:
            return False
        client.chat.completions.create(
            model=resolved or model, messages=[{"role": "user", "content": "ping"}],
            max_tokens=1, timeout=PROBE_TIMEOUT_S)
        return True
    except Exception as exc:  # offline, rate-limited, no credits, ...
        logger.debug("probe %s failed: %s", _label(route), exc); print("  PROBE-ERR", _label(route), type(exc).__name__, str(exc)[:200]) if __import__("os").environ.get("MR_DEBUG") else None
        return False


def _probe_all(routes) -> list[bool]:
    """Probe in parallel so the wait is at most ~PROBE_TIMEOUT_S, not the sum."""
    if not routes:
        return []
    with cf.ThreadPoolExecutor(max_workers=min(6, len(routes))) as ex:
        return list(ex.map(_probe, routes))


def _status(agent, msg: str) -> None:
    for name in ("_emit_diagnostic_status", "_buffer_diagnostic_status"):
        fn = getattr(agent, name, None)
        if callable(fn):
            try:
                fn(msg)
                return
            except Exception:
                pass


# ------------------------------------------------------------ automatic ---
def _climb(agent, primary, chain) -> None:
    """On an automatic fallback: switch to the best route above the current one that answers."""
    cur_idx = max(0, int(getattr(agent, "_fallback_index", 0) or 0) - 1)
    cur_model, cur_prov = getattr(agent, "model", ""), getattr(agent, "provider", "")
    # Where are we in the chain (by name, more robust than the index)?
    for i, r in enumerate(chain):
        if _same(r[0], r[1], cur_prov, cur_model):
            cur_idx = i
            break
    candidates = [primary] + list(chain[:cur_idx])
    ok = _probe_all(candidates)
    if not any(ok):
        return
    best = ok.index(True)
    if best == 0:
        # Primary answers: lift Hermes' cooldown so its own restore puts the primary back.
        agent._rate_limited_until = 0
        agent._rate_limit_backoff_count = 0
        if _ORIG(agent):
            _status(agent, f"model-return: {_label(primary)} is available again, switched back to it.")
        return
    target = chain[best - 1]
    from agent.chat_completion_helpers import try_activate_fallback
    agent._fallback_index = best - 1  # try_activate_fallback activates chain[_fallback_index]
    if try_activate_fallback(agent, None):
        _status(agent, f"model-return: switched up to {_label(target)}, the best model available right now.")


# --------------------------------------------------------------- manual ---
def _manual(agent, primary, chain) -> None:
    rt = getattr(agent, "_primary_runtime", None) or {}
    key = f"{rt.get('provider')}|{rt.get('model')}"
    if getattr(agent, "_mr_manual_key", None) != key:
        agent._mr_manual_key, agent._mr_turns = key, 0
    agent._mr_turns = getattr(agent, "_mr_turns", 0) + 1
    if agent._mr_turns % EVERY_N_PROMPTS:
        return
    chosen = (str(rt.get("provider") or ""), str(rt.get("model") or ""))
    pos = next((i for i, r in enumerate(chain) if _same(r[0], r[1], *chosen)), None)
    above = [primary] + (list(chain[:pos]) if pos is not None else list(chain))
    ok = _probe_all(above)
    available = [r for r, good in zip(above, ok) if good]
    name = f"{chosen[1]} ({chosen[0]})"
    if pos is not None:
        if not available:
            return
        note = (f"You are still on {name}, which you chose by hand and is one of your fallbacks. "
                f"Available right now above it: {', '.join(_label(r) for r in available)}. "
                f"To switch: /model {available[0][1]} --provider {available[0][0]}")
    else:
        back = available[0] if available else primary
        note = (f"You are still on {name}, which you chose by hand (not one of your fallbacks). "
                f"Keep it, or go back to {_label(back)}"
                + (" (available right now)" if available else " (not answering right now)")
                + f"? To go back: /model {back[1]} --provider {back[0]}")
    with _lock:
        _notes[str(getattr(agent, "session_id", ""))] = note


# ------------------------------------------------------------------ hooks ---
def _patched_restore(agent) -> bool:
    restored = _ORIG(agent)
    try:
        primary, chain = _config_routes()
        rt = getattr(agent, "_primary_runtime", None) or {}
        manual = bool(primary[1]) and not _same(rt.get("provider"), rt.get("model"), primary[0], primary[1])
        if manual:
            _manual(agent, primary, chain)
        elif getattr(agent, "_fallback_activated", False) and getattr(agent, "_provider_fallback_active", False):
            _climb(agent, primary, chain)
    except Exception as exc:
        logger.warning("model-return skipped this prompt: %s", exc)
    return restored


def _on_pre_llm_call(session_id=None, **_):
    with _lock:
        note = _notes.pop(str(session_id or ""), None)
    if not note:
        return None
    return {"context": "[model-return plugin] At the very END of your reply, add this note for the user on its "
                       "own line, translated to the language you are replying in, keeping the /model command "
                       f"exactly as written: {note}"}


def register(ctx) -> None:
    global _ORIG
    import agent.agent_runtime_helpers as arh
    if getattr(arh.restore_primary_runtime, "_model_return", False):
        return  # already installed (plugin reload)
    _ORIG = arh.restore_primary_runtime
    _patched_restore._model_return = True
    arh.restore_primary_runtime = _patched_restore
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
