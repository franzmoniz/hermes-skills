---
name: hermes-model-return
description: "Use when installing/checking the model-return plugin. Every prompt, climbs back to the primary or best fallback; respects manual /model."
version: 1.0.0
author: Francisco Moniz (@franzmoniz)
license: MIT
---

# Hermes Model Return

Installs the `model-return` Hermes plugin (code in `plugin/model-return/`). See README.md for what it
does. Ask the user before installing; never change their model or fallback settings.

## Install

1. Find HERMES_HOME (`hermes config path` or the env var). Check whether
   `<HERMES_HOME>/plugins/model-return` already exists; if it does, compare `plugin.yaml` versions and
   only replace it if this one is newer.
2. Back up `config.yaml` (`config.yaml.bak-<timestamp>`).
3. Copy `plugin/model-return/` to `<HERMES_HOME>/plugins/model-return/`.
4. `hermes plugins enable model-return`, then `hermes plugins list` must show it `enabled`.
5. Read `model:` and `fallback_providers:` in config.yaml and tell the user the order the plugin will
   climb (primary first, then fallbacks top to bottom). If there is no `fallback_providers`, say the
   plugin only helps manual-choice reminders until they add fallbacks.

## Verify (no cost)

Run with Hermes' own Python (bootstrapped so dependencies load):

```python
import sys; sys.path.insert(0, "<hermes-agent dir>"); import hermes_bootstrap
from hermes_cli.plugins import get_plugin_manager
m = get_plugin_manager(); m.discover_and_load(force=True)
import agent.agent_runtime_helpers as a
print(getattr(a.restore_primary_runtime, "_model_return", False), m.has_hook("pre_llm_call"))
```

Both must be True. To see why a route is not considered available, set `MR_DEBUG=1` and call the
plugin's `_probe(("provider", "model", "base_url"))`: it prints the provider's error.

## Pitfalls

- A route that fails the test is never chosen, so check broken fallbacks (expired logins, models not
  on the user's plan) and report them; the plugin cannot fix logins.
- Do not test by running plugin code under a Python without Hermes' dependencies: Hermes relaunches
  itself and the test results are meaningless. Always `import hermes_bootstrap` first.
- Uninstall: `hermes plugins disable model-return` and delete the folder.
