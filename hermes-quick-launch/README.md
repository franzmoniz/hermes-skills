# Hermes Quick Launch - Open Hermes from Win+R

**Author:** Francisco Moniz ([@franzmoniz](https://github.com/franzmoniz))
**License:** MIT  -  **Version:** 0.1.0  -  **Windows only**

## What it does

Press **Win+R**, type **`hermes`**, press Enter. Hermes opens right away in Windows Terminal (or in
PowerShell if you don't have Terminal), in your home folder. No more opening a terminal and typing the
command.

- Per user, no administrator rights, costs nothing, and you can undo it.
- If you use [Hermes Device Sync](../hermes-device-sync), Win+R also continues your latest
  conversation from any of your devices, because it runs the same `hermes` command as your terminal.
- You can pick another word instead of `hermes`.

## How to install

Open Hermes and send:

> Install the skill in the folder `<path to hermes-quick-launch>` (or download it from
> https://github.com/franzmoniz/hermes-skills, folder hermes-quick-launch) and follow its SKILL.md.
> Check what I already have first.

Or do it yourself in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
# another word:  ... install.ps1 -Name herm
```

Then press Win+R, type `hermes`, and press Enter.

## What your Hermes does (summary of SKILL.md)

1. Checks first: that you are on Windows, that Hermes is installed, and whether Win+R `hermes` already
   exists. If it does, it only offers a test. If the name points to something else, it asks you before
   replacing it.
2. Runs `scripts/install.ps1`, which:
   - copies `hermes-launch.vbs` to `%LOCALAPPDATA%\hermes\`, backing up an older one;
   - sets the per-user registry key
     `HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\hermes.exe` to that file. Win+R uses this
     key to find names;
   - tells you if Windows Terminal is missing (optional) or if PowerShell profiles are blocked. This
     only matters if you have a `hermes` wrapper in your profile.
3. Asks you to test it.

Why a `.vbs`: it starts Terminal without an extra black console window flashing.

## Uninstall

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

It removes only the registry key and the launcher this skill created.
