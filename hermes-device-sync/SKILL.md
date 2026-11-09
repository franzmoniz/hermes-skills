---
name: hermes-device-sync
description: Link devices into one Hermes (sync, hand-off, queue).
version: 0.4.0
author: Francisco Moniz (franzmoniz), Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [sync, multi-device, github, handoff, fallback, tailscale, ssh, offline, ollama]
    related_skills: []
---

# Hermes Device Sync - One Hermes on all your devices

Makes every device of ONE person (laptop, desktop, server, phone running Hermes) behave like the same
Hermes: shared memory and the skills the user created, the newest conversation follows you to whichever
device you open (saved seconds after EVERY answer, so closing the terminal loses nothing), an activity
log of all conversations, the same AI accounts, logins and fallback chain everywhere (checked
automatically), file sharing, and a queue to leave work for a device that is off. Optional: control one device from another over SSH (home network or Tailscale).
Transport is a PRIVATE GitHub repo of the user. Syncing uses no model tokens.

Check first, never assume. Do not assume the user has anything (GitHub account, git, Tailscale, logins),
and do not assume they have nothing either: CHECK each item on this device before acting, reuse what
already exists, and install/create/log in ONLY what is missing. Never reinstall, re-create or re-login
something that already works (no second repo, no second cron job, no duplicate profile block, no second
GitHub/Tailscale login). The user may not be technical: explain each thing you ask them to do in one
plain sentence.

## When to Use
- The user gives you this folder, or asks to link/sync Hermes across devices, continue a chat on another
  device, check that devices have the same AI accounts, leave a task for another device, or control one
  device from another.
- Later, day to day: "leave this for <device>", "sync now", "are my devices the same?", "add my phone".
- Don't use for: sharing one Hermes between DIFFERENT people (this is one person's devices only).

## Hard rules
1. Never put secrets in the repo (API keys, tokens, passwords, auth.json, .env). The repo holds names only.
   Each device logs in to its AI providers and services itself (`hermes auth add <provider>`, the
   Google Workspace login, etc.). NEVER copy auth.json, .env tokens or OAuth token files between
   devices: copied OAuth tokens get revoked within days (Google, Anthropic...) and can break BOTH devices.
2. Never type or store passwords yourself; the user completes logins in the browser (device codes).
3. Never add a paid model/API or enable anything that can bill the user without asking. Ask how they pay
   for AI (subscriptions, free tiers, pay-per-token) before proposing a fallback chain or the recap.
4. Back up any file you change outside the repo (`<file>.bak-YYYYMMDDHHMM`); setup.py already does this.
5. Ask before system-level changes (PowerShell execution policy, SSH server, firewall, Tailscale).
6. If a device is in someone else's network (e.g. a work/team Tailscale), never touch other people's
   machines; only talk between the user's own devices.
7. Re-read files / re-run checks before saying something is done. If a Hermes session starts with
   "No <provider> credentials found", it is silently running on a fallback model: tell the user.

## Files in this folder
- `scripts/setup.py` installer for one device (idempotent). `scripts/sync.py` one sync round.
- `scripts/turn_sync.py` run by the Hermes hook after every answer (background, no windows, no tokens).
- `scripts/memory_sync.py`, `skills_sync.py`, `device_check.py` (AI setup + logins check), `jobs.py`
  (queue), `handoff.py` (conversation, recap, activity log), `share.py` (files), `remote.py` (SSH), `common.py`. All stdlib Python; run them with the Python that runs Hermes.
- `templates/` shell wrappers, `config.example.json`, `windows-ssh-server.ps1`, `gitignore`.
- `README.md` the human guide (show the user the relevant parts when they ask "what is this?").

## Procedure: first device

Step 0 - Explain and plan. Tell the user in 3-4 lines what they get (see README "What you get"). Ask:
(a) which devices and their OS, (b) a short unique name per device ("Laptop", "Desktop", "Phone"),
(c) how they pay for AI. Done when you have the device list and names.

Step 0b - Inventory (do this BEFORE installing anything). Run these checks with `terminal` and keep
the results; every later step starts with "skip if the inventory says it is done":
- Already linked? `$HERMES_HOME/hermes-sync.json` exists -> this device is already set up: run
  `python <data_dir>/scripts/sync.py`, report the warnings and fix only those. Do NOT rerun the procedure.
- Skill installed? `$HERMES_HOME/skills/hermes-device-sync/SKILL.md`.
- Tools: `git --version`, `gh --version`, `python --version` (or the Hermes Python).
- GitHub: `gh auth status` (logged in? which account?). Existing sync repo: `gh repo list --limit 200`
  and, for a likely candidate, `gh api repos/<owner>/<repo>/contents/hermes-sync` (exists = another
  device already set it up -> follow "every other device" instead). Existing local clone: look for a
  folder with `hermes-sync/scripts/sync.py` in the home folder.
- Hermes: `hermes --version`, `hermes auth list` (AI accounts), `hermes config get model.default`,
  `hermes config get fallback_providers`, `hermes cron list` (a `hermes-sync` job already?),
  `hermes gateway status`.
- Optional parts: `tailscale status` (installed? logged in? which tailnet?), SSH server listening on 22.
Show the user a short summary ("already have: ..., missing: ...") and only then continue.

Step 1 - Install the skill (skip if already installed). If you only have the GitHub link, download
`https://github.com/franzmoniz/hermes-skills/archive/refs/heads/main.zip` (works without git:
`curl -L -o hs.zip <url>` or PowerShell `Invoke-WebRequest <url> -OutFile hs.zip`), unzip it and use
its `hermes-device-sync/` folder.
Copy this folder to `$HERMES_HOME/skills/hermes-device-sync/` (Windows:
`%LOCALAPPDATA%\hermes\skills\hermes-device-sync\`) if it is not there. Done when SKILL.md exists there.

Step 2 - Tools (only the ones the inventory found missing):
- Windows: `winget install --id Git.Git -e` and `winget install --id GitHub.cli -e` (then open a new terminal)
- macOS: `brew install git gh`   - Debian/Ubuntu: `sudo apt install git gh`   - Termux: `pkg install git gh python openssh`
Done when both commands print a version.

Step 3 - GitHub (skip the parts already done). If `gh auth status` already shows a login, use it (confirm
the account with the user). Otherwise ask if they have an account; if not, they create one at
https://github.com/signup (free). Then `gh auth login --hostname github.com --git-protocol https --web` and tell them to open the link and
type the code shown. Then `gh auth setup-git` (git then uses gh's token, which also works over SSH and
from cron without prompts; harmless if already configured). Done when `gh auth status` shows them logged in.

Step 4 - Private repo. If the inventory found a sync repo or a local clone, reuse it (and `git pull`).
Otherwise ask for a name (default `hermes-sync`), check it does not exist (`gh repo view <name>`), then
`gh repo create <name> --private` and `gh repo clone <name> <home>/<name>`. If they already have a private repo they want to reuse (e.g. notes),
that works too: the tool lives in a subfolder. Done when the clone exists. NEVER make it public.

Step 5 - Run setup (idempotent: safe if parts already exist; it keeps an existing cron job, replaces
its own profile block instead of adding a second one, and never overwrites config.json). `python <this folder>/scripts/setup.py --repo <clone> --device "<name>"` using the
Python that runs Hermes (`python` usually works; on Windows the Hermes venv Python is fine).
It copies the tool into `<clone>/hermes-sync/`, writes the device config, the cron bootstrap, the
`hermes` shell wrapper and the cron job, and does the first sync. Read every `setup:` and
`hermes-sync:` line. If it warns about the PowerShell execution policy, ask the user, then run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Done when it ends with "first sync OK".

Step 6 - Make sure cron runs. The 15-minute job only runs while the Hermes gateway runs. Check
`hermes cron status` and `hermes gateway status`; if it is already installed/running, leave it. If not installed: `hermes gateway install` (must be run in the user's own
desktop session, not over SSH) and start it. Done when `hermes cron list` shows `hermes-sync` and,
after its next run, "Last run: ... ok".

Step 7 - Shared settings (`<clone>/hermes-sync/config.json`, applies to ALL devices):
- `fallback_providers`: list of `{"provider","model"}` to use when the primary model fails or runs out
  (an entry may also have `"base_url"`, for a local/custom endpoint such as Ollama; never put keys here).
  Build it only from providers the user has (`hermes auth list`) and is happy to use (rule 3). Leave
  `null` to not manage it. When set, every device applies it on its next sync (with a config backup).
- `summary`: 3-line recap shown above a resumed conversation. Costs a small model call each time the
  user exits Hermes, so enable it only with a provider the user accepts (a free one if they want zero
  cost). Set `language` to the user's language.
- `queue.rules`: extra rules for unattended requests (e.g. "never delete files outside ~/projects").
Save, then `python <clone>/hermes-sync/scripts/sync.py`. Done when the sync prints no errors.

Step 7b - Logins and access. The sync compares, by NAME only, everything each device is connected to:
AI providers, keys in `$HERMES_HOME/.env` and `*.env`, MCP servers, and Google Workspace accounts (it
also tests each Google login, so an expired one is reported). For every line "missing ..." or
"Google account ... is expired": do the login yourself when it needs no user action, otherwise ask the
user and walk them through it (they type passwords/codes in the browser, never in chat). Key values
come from the user (or wherever they keep them), never from the repo.
Done when the sync prints no "missing"/"expired" lines.

Step 8 - Tell the user what is left: install on the other devices (next procedure). Give them the
exact prompt from README "Adding another device".

## Procedure: every other device
1. Hermes must already be installed there. Do Step 0b (inventory) here too, then Steps 2 and 3 only
   for what is missing (`gh` must be logged in with the SAME GitHub account as the first device).
2. If the repo is not cloned yet: `gh repo clone <name> <home>/<name>` (else `git pull` in it) - the tool is already inside it (`<clone>/hermes-sync/`), so this
   device does not need the original folder: copy `<clone>/hermes-sync/` to the skills dir (Step 1).
3. `python <clone>/hermes-sync/scripts/setup.py --repo <clone> --device "<unique name>"`, then Step 6.
4. AI accounts: the sync prints `... is missing AI accounts that <device> has: x, y`. Only those are
   missing (the others are already logged in; don't touch them). For each missing one, guide
   the user through `hermes auth add <provider>` (or `hermes model` / the provider's login). Plugins:
   some providers need a plugin first (e.g. GitHub Copilot: `hermes plugins install github-copilot`).
   Primary model: `hermes config set model.default <model>` / `model.provider` like the other device.
5. Logins and access: same as Step 7b (Google accounts, .env keys, MCP servers, plugins). Each must be
   logged in HERE; don't copy token files from the other device.
6. Run `sync.py` again until it prints no "missing" / "different" / "expired" lines. Done = no warnings.

## Optional: control one device from another (SSH)
Only if the user wants it (e.g. "from the laptop at school, do X on my desktop at home").
1. Same network only (home): no extra account. Anywhere: Tailscale (free personal plan). First check
   `tailscale status` on each device: if it is already installed and logged in, don't reinstall or log in
   again. Only where missing:
   install (Windows `winget install --id Tailscale.Tailscale -e`, macOS/Linux see tailscale.com/download),
   then `tailscale up` and log in with the SAME account on all devices. A device can be in only ONE
   tailnet at a time: if one is already in a work/team tailnet, explain the choice (move it, or join
   the user's devices to that tailnet, or ask the tailnet owner to share a machine) and let them decide.
   If the tailnet has machines of other people: `tailscale set --accept-routes=false` and rule 6.
2. Target device needs an SSH server (check first: something listening on port 22 = already there). Windows: elevated PowerShell
   `templates/windows-ssh-server.ps1 -AllowFrom <controller tailscale IP>` (firewall allows only the
   home LAN + those IPs). Linux: `sudo apt install openssh-server`. macOS: System Settings > Sharing >
   Remote Login. Phones: usually not a target.
3. Controller: `python scripts/remote.py keygen` (it does nothing if the key exists), sync. Target: sync, then
   `python scripts/remote.py authorize "<controller>"` (on Windows admin accounts it tells you to rerun
   the .ps1 with `-AuthorizeKey`). Sync again so addresses are fresh.
4. Test from the controller: `remote.py check "<target>"` -> "online via ..."; then
   `echo 'hostname' | python scripts/remote.py run "<target>"`. Done when it prints the target's name.

## Optional: answer offline with a local model (Ollama)
Without internet every cloud model fails, so Hermes cannot answer at all. Sync already keeps offline
work (see Pitfalls); this adds a free LOCAL model as the LAST fallback so Hermes still answers offline.
Online nothing changes: the local model is only used when everything before it fails. Ask first (it
downloads several GB and is much weaker than cloud models, especially with tools).
1. Check the hardware of EACH device (read only): RAM, GPU and its VRAM (`nvidia-smi` if present),
   free disk. Windows: `Get-CimInstance Win32_ComputerSystem, Win32_Processor, Win32_VideoController`
   and `Get-PSDrive C`. A device that is off or far away: leave it a read-only request (`jobs.py add`).
2. Pick a model per device by GPU memory (the model must fit in VRAM to be usable): ~4 GB -> a 3-4B
   model (e.g. `qwen3:4b`); ~8 GB -> `qwen3:8b`, or `qwen3:30b-a3b` (MoE) with 32 GB RAM; no GPU ->
   a 1-4B model, slow. Prefer models with tool calling. Check free disk (models are 2-20 GB).
3. Install Ollama only where missing (`ollama --version` first). Windows:
   `winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements`
   (from Hermes' bash add `< /dev/null`, else winget fails with "stdin is not a tty"; binary in
   `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`). macOS: `brew install ollama`. Linux: the script
   from ollama.com/download.
4. Hermes rejects models with less than 64K context, so set it for the server: Windows
   `setx OLLAMA_CONTEXT_LENGTH 65536`, macOS/Linux export it where the server starts. Start the
   server (`ollama serve`; on Windows the tray app alone may not start the API: run `ollama.exe serve`
   hidden). Check: `curl http://localhost:11434/api/version`.
   Do NOT use the Ollama app's "launch Hermes Agent" integration: it rewrites config.yaml and makes the
   local model the PRIMARY one (and limits toolsets). If it happened, restore config.yaml from a backup.
   Small GPU: `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q4_0` halve the memory of a 64K context.
5. `ollama pull <model>`, then give it the SAME alias on every device: `ollama cp <model> hermes-local`.
   Each device can use a different model size; the shared chain names only the alias.
6. Add it LAST in `config.json` `fallback_providers`:
   `{"provider": "custom", "model": "hermes-local", "base_url": "http://localhost:11434/v1"}` and sync.
   Every device applies it; a device whose local server or model is missing prints a warning on sync.
7. Test once with the internet off (or with a wrong primary model in a throwaway session): Hermes
   should answer through `hermes-local`. Delete test sessions afterwards.

## Day-to-day commands (run with `terminal`, paths relative to `<clone>/hermes-sync/`)
- Sync now: `python scripts/sync.py` (the user can type `Sync-Hermes` in PowerShell / `sync-hermes` in bash).
- Leave work for another device: `python scripts/jobs.py add "<device>" "<self-contained task>"`, then
  sync. If `remote.py check "<device>"` is online, also `remote.py sync "<device>"` to start it now.
  The task must be self-contained (the other Hermes has no access to this chat). Results:
  `queue/<id>.result.md`; `jobs.py list` for status. Read results to the user when sync reports them.
- Same setup everywhere? Read `devices/*.json` (AI + `access`) and run a sync; report every warning
  line and fix it (Step 7b).
- Files between devices: if both devices are logged in to the same cloud drive (e.g. Google Drive via
  the google-workspace skill), use the drive. Otherwise `python scripts/share.py put <file> "<note>"`
  (max 50 MB), sync, and on the other device `share.py get <name>`. If the file is on a device that
  is off or far away, leave it a request: `jobs.py add "<device>" "Share <path> with
  hermes-sync/scripts/share.py put"` - it uploads when that device is on. `share.py rm` when done.
- What happened on other devices: read `activity.md` (one line per conversation, newest first).
- Skills: skills the user creates on any device (`skill_manage`) reach all devices on the next sync.
  Bundled and hub-installed skills are not copied (each Hermes manages those); if a device lacks a hub
  skill the other has, install it there with `hermes skills install`.
- The user opens Hermes by typing `hermes` with no arguments: it syncs, resumes the newest conversation
  from any device, and syncs again on exit. `hermes-new` = a fresh Hermes without that.

## Pitfalls
- Working offline (no internet): Hermes itself only answers offline with a LOCAL model (e.g. Ollama) in
  the fallback chain (see "Optional: answer offline"); cloud models need internet. Everything done offline is still kept: the conversation
  stays in Hermes' local database with the time of every message, the activity line is written at the
  time the conversation HAPPENED (not when it is synced), and every sync commits locally and quietly
  skips the push. When the device is online again, the next sync pushes it all, merges the activity
  logs of both devices without conflicts (git `merge=union` + tidy/sort), and makes the recaps that were
  left "(recap pending)". Nothing extra to clean up: there is no separate offline folder.
- Saving happens after EVERY answer (hook `post_llm_call` -> `turn_sync.py`, seconds later); the
  15-min cron job is only a safety net and runs the queue while nobody chats. An answer cut off
  mid-way (terminal closed while it was still writing) is not saved; everything before it is.
- Hooks must not open windows: on Windows background processes use CREATE_NO_WINDOW (not
  DETACHED_PROCESS, which makes every child process pop up a console).
- A device that lacks the primary provider runs on the fallback chain WITHOUT saying so in answers; the
  banner "No <provider> credentials found" is the only sign. Check `devices/*.json` after setup.
- Conversation hand-off uses Hermes internals (`state.db`, `hermes sessions export --format trace`,
  `hermes sessions import --from claude`). If a Hermes update changes them, sync prints
  "conversation export failed" and everything else keeps working. Hermes Desktop app chats are not handed off.
- Queue requests run with `--yolo` (no confirmations, nobody is there). Keep tasks specific; put limits
  in `queue.rules`. Do not pass `--source` to `hermes chat` (fails with invalid_params on some versions).
- Windows: the cron bootstrap is a tiny `.sh` (run by Hermes' bash); the real code lives in the repo, so
  updating the repo updates every device. Do not edit `$HERMES_HOME/scripts/hermes-sync.sh` by hand;
  rerun setup.py. PowerShell profile path may be under OneDrive (setup.py asks Windows for it).
- Windows OpenSSH ignores `~/.ssh/authorized_keys` for administrator accounts (use the .ps1). Commands
  that wait for input (git credential prompts, winget, hermes) hang over SSH: use `gh auth setup-git`
  and non-interactive flags.
- Sync conflicts inside the sync folder are auto-resolved (remote wins; memory is re-merged from the
  device's own copy). Conflicts in other files of a reused repo are reported, never auto-resolved.
- Google Workspace logins that expire every ~7 days on every device: the user's Google Cloud OAuth app is
  in "Testing" mode (refresh tokens of test apps expire after 7 days). Fix once, with the user: Google
  Cloud console > Google Auth Platform > Audience > "Publish app" (personal use needs no verification;
  Google shows an "unverified app" screen at login, which is expected). Then log in again on each device.
- Copying `auth.json`/`.env` between devices is NOT supported: OAuth refresh tokens can rotate and
  break both devices. Log in on each device.
- Phone: works if Hermes runs on it as a normal install (e.g. Termux on Android: `pkg install python git gh`,
  run setup with the bash wrapper; the gateway must be running for cron). A phone app that cannot run
  scripts cannot join; reach the other devices through its messaging gateway instead.

## Verification
- `python scripts/sync.py` prints nothing (or only expected lines) on every device.
- `devices/` has one JSON per device with the same `providers`, `model` and `fallback`.
- `hermes cron list` shows `hermes-sync` with a recent "ok" run on every device.
- Hand-off: write one message in `hermes` on device A, exit, open `hermes` on device B: the same
  conversation resumes there.
- Offline model (if set up): `curl http://localhost:11434/v1/models` lists `hermes-local` on every
  device, and sync prints no "local model" warning.
- Queue: `jobs.py add "<B>" "Run hostname and tell me the result"` on A, sync A, sync B, wait ~1 min,
  sync B, sync A: A prints "request to B done" and the result file has B's hostname.
