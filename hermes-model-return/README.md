# Hermes Model Return - *always back to your best AI model*

**Author:** Francisco Moniz ([@franzmoniz](https://github.com/franzmoniz))  -  **License:** MIT

## The problem

Hermes has a fallback chain: when your main model (the *primary*) fails, it moves to the next one
(for example Claude -> Copilot -> free models -> a local Ollama model). But going back up is slow:

- if the primary failed because of a **rate limit / no credits**, Hermes waits for a cooldown
  (1 min, 2, 4 ... up to **4 hours**) before it even tries the primary again, even if your credits
  came back an hour earlier;
- it **never climbs to a better fallback**: if you ended up on the local model, you stay there even
  when a better online fallback works again.

## What this does

At the start of **every prompt**, while you are not on your primary:

1. It sends a tiny test (1 token) to the primary and to every fallback **above** the one you are on.
2. The best one that answers wins: Hermes switches to it right away, for this prompt.
   You see a short status line saying so.

Works online or offline: with no internet the tests fail in about a second and nothing changes.

### Manual choices are respected

If **you** switched model by hand (`/model ...`), the plugin **never switches for you**. Instead,
every **5th prompt**, the reply ends with a short note:

- your model is one of your fallbacks -> which better models are available right now, and the
  `/model` command to switch;
- your model is not a fallback -> a question: keep it, or go back to the primary (or to the best
  fallback that is available right now), with the `/model` command.

## Install

Tell your Hermes:

> Install the skill `hermes-model-return` from https://github.com/franzmoniz/hermes-skills and follow
> its SKILL.md.

Or by hand: copy `plugin/model-return` to `<HERMES_HOME>/plugins/model-return` and run
`hermes plugins enable model-return`.

## Uninstall

`hermes plugins disable model-return` (and delete `<HERMES_HOME>/plugins/model-return`).

## Good to know

- **Cost:** each test is one request with 1 output token. On free/local models that is free; on
  subscriptions (Claude, Copilot) it uses a tiny bit of your quota. It only runs while you are on a
  fallback, never while you are on the primary. It never spends money by itself.
- **Speed:** tests run in parallel, max ~8 s per prompt (usually ~1 s).
- **Safety:** if anything in the plugin fails, Hermes simply behaves as if it was not installed.
- It hooks into Hermes' own "restore the primary at the start of a turn" step. A big Hermes update
  could rename that step; then the plugin does nothing (it does not break Hermes) until updated.
- A fallback that is broken (logged out, model not available on your plan) simply never wins.
