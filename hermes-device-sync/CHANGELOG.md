# Changelog - Hermes Device Sync

Format: one section per version, newest first. Groups: Added, Changed, Fixed, Removed.

## 0.7.0 - 2026-11-11
### Changed
- The sync is now only the sync. "`hermes` always continues the same conversation, with a recap" moved
  to its own skill, **Hermes's Terminal** (folder `hermes-terminal`), so people with one device can
  use it too. After this update `hermes` still syncs, but opens a new conversation unless you install
  Hermes's Terminal: install it to keep continuing the same conversation (the two combine by themselves,
  and it takes over your recap settings).
- `hermes` is now a shared launcher that several skills plug into (block `hermes-launcher` in your
  shell profile); the sync adds its steps before Hermes opens and after it closes.
### Removed
- The recap settings (`summary` in config.json) and `handoff.py summarize/prepare`: now in Hermes's Terminal.
  New setting `language` for the sync's own messages.

## 0.6.0 - 2026-11-11
### Added
- One Hermes at a time: when you type `hermes` and Hermes is already open on another of your devices,
  you are asked to close it there and continue here, or to close this terminal (`presence.py`).
- `presence.py guard "<device>"`: before your Hermes opens Hermes on another device by itself
  (remote checks, queued work) it checks the request queue and its rules first, then whether Hermes
  is open there, and asks you if it is.
- `presence.py status` shows on which devices Hermes is open.
- Before Hermes opens, the `hermes` wrapper asks about updates of your Hermes's Skills (when
  hermes-skills-updater is installed).
### Changed
- Each device record now also publishes its Python path and scripts folder (needed to check and close
  Hermes on another device over SSH).

## 0.5.0 - 2026-11-09
### Added
- Optional encrypted vault sync (`vault_sync.py`): the same saved logins on every device. The key never
  goes to the repo; items are merged one by one, deletions are kept.

## 0.4.0 - 2026-11-09
### Added
- Offline answers: optional local model (Ollama) as the last fallback, with a check that it is installed
  and running. The fallback chain shared by all devices keeps each entry's base_url.
- Tips for the Ollama app (sign in first, then close the agent picker screen) and for small GPUs (KV cache).
### Fixed
- Warning against the Ollama app's "launch Hermes" option, which breaks the setup.

## 0.3.0 - 2026-11-09
### Added
- Work done offline is kept and placed at the right date when the device is back online.
- Pending recaps are written when the device is online again.
### Fixed
- Activity log merges without conflicts between devices.
- Google login check uses Hermes' own Python (no more false "expired").

## 0.2.0 - 2026-11-09
### Added
- First public version: shared memory and skills, conversation hand-off between devices, same AI setup
  check, request queue for devices that are off, file sharing, optional remote control over SSH.
