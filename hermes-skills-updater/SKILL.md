---
name: hermes-skills-updater
description: "Use when installing any skill from franzmoniz/hermes-skills or the user asks about skill updates. Checks, explains, asks, updates."
version: 0.1.0
author: Francisco Moniz (franzmoniz), Hermes Agent
license: MIT
platforms: [windows, linux, macos]
---

# Hermes Skills Updater

Keeps the skills installed from https://github.com/franzmoniz/hermes-skills up to date, always asking
the user first. Code: `scripts/updater.py` (stdlib), plugin `plugin/skills-updater/`.

## Install (once per device; every skill of this repo asks for it at the end of its own install)
1. Check first: `<HERMES_HOME>/plugins/skills-updater` and `<HERMES_HOME>/scripts/hermes-skills-updater.py`
   exist and `hermes plugins list` shows `skills-updater` enabled -> already installed, stop.
2. Ask the user: "Do you want to be asked about updates of these skills when Hermes starts?" Only if yes:
3. Copy this folder to `<HERMES_HOME>/skills/hermes-skills-updater/` (if it is not there yet).
4. `python scripts/post_update.py` (copies the updater and the plugin into place), then
   `hermes plugins enable skills-updater`.
5. `python <HERMES_HOME>/scripts/hermes-skills-updater.py status` must list the installed skills.

## Day to day
- At the first prompt of each session the plugin injects the list of updates with their changelog.
  Before answering, summarise each update for the user (added / changed or improved / fixed / removed)
  and ask yes/no per skill. Yes -> `python <HERMES_HOME>/scripts/hermes-skills-updater.py apply <skill>`.
  No -> `... decline <skill> <version>` (asked again only for a newer version). Report the output.
- The user can also ask any time: run `... check` (JSON) and present it the same way.
- Users of Hermes Device Sync: the `hermes` wrapper asks in the terminal before Hermes opens
  (`... prompt`), and answers are shared through the sync repo (`skill-updates.json`): updates accepted
  on one device are applied on the others without asking; declined versions are not asked again.

## Rules
- Never update without the user's yes for that version (or a yes given on another of their devices).
- Updates keep a backup in `<HERMES_HOME>/backups/skills-updater/`. To undo: unzip it over the skill folder.
- Offline: nothing is asked; Hermes works normally.

## Uninstall
`hermes plugins disable skills-updater`; delete `<HERMES_HOME>/plugins/skills-updater`,
`<HERMES_HOME>/scripts/hermes-skills-updater.py` and the skill folder.
