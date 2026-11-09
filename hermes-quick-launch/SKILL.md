---
name: hermes-quick-launch
description: Open Hermes from Win+R by typing hermes.
version: 0.1.0
author: Francisco Moniz (franzmoniz), Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [windows, launcher, win-r, terminal, shortcut]
    related_skills: []
---

# Hermes Quick Launch - Open Hermes from Win+R

Press Win+R, type `hermes`, Enter: Windows Terminal opens (plain PowerShell if Terminal is missing) in
the home folder and starts Hermes. Per-user, no admin rights, nothing paid, fully reversible. If the
user has a `hermes` wrapper in their PowerShell profile (for example from hermes-device-sync), that
wrapper is what runs.

## When to Use
- The user gives you this folder, or wants a quick way to open Hermes on Windows (Win+R, "a shortcut").
- Don't use for: macOS/Linux (no Win+R; suggest a shell alias or a launcher of their desktop instead).

## How it works
- `scripts/hermes-launch.vbs` starts `wt.exe -d %USERPROFILE% powershell.exe -NoExit -Command hermes`
  (or the same command in plain PowerShell). A .vbs is used so no extra console window flashes.
- Win+R resolves names through the per-user registry key
  `HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\hermes.exe`; its default value points to
  the .vbs copied into `%LOCALAPPDATA%\hermes\` (or `$HERMES_HOME`).

## Procedure
1. Check first (never assume, never reinstall what works), with `terminal`:
   - Windows? Hermes installed (`hermes --version`)?
   - Already set: `reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\hermes.exe"`.
     If it already points to `...\hermes\hermes-launch.vbs`, tell the user it is already installed and
     only offer to test it. If it points elsewhere, tell the user what it points to and ask before
     replacing it.
   - Windows Terminal present (`%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe`)? If not, it still works in
     plain PowerShell; installing Terminal is optional (`winget install --id Microsoft.WindowsTerminal -e`),
     ask first.
2. Install: `powershell -NoProfile -ExecutionPolicy Bypass -File <this folder>/scripts/install.ps1`
   (add `-Name <word>` if the user wants another word than "hermes"). It is idempotent and backs up an
   older launcher. Done when it prints "done".
3. If it warns that PowerShell profiles are blocked AND the user has a `hermes` wrapper in the profile,
   ask, then `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
4. Test: ask the user to press Win+R, type the word, Enter. Done when Hermes opens.

## Uninstall
`powershell -NoProfile -ExecutionPolicy Bypass -File <this folder>/scripts/uninstall.ps1` (removes only
what this skill created).

## Pitfalls
- Win+R names come from App Paths: the key name must end in `.exe` (`hermes.exe`) even though it points
  to a .vbs. HKCU needs no admin.
- The command runs in the user's home folder, not in the last working folder.
- If `hermes` is not on PATH for new terminals (fresh install, terminal not restarted), the window opens
  with "hermes not recognized": sign out/in or restart Explorer once.

## Verification
- `reg query` shows the key pointing to the launcher, the launcher file exists, and Win+R opens Hermes.
