<#
Hermes Quick Launch - install. Makes Win+R -> "hermes" open Hermes in Windows Terminal.
Per-user, no administrator rights needed. Safe to run again (checks first, changes only what differs).

  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 [-Name hermes]

-Name   the word you type in Win+R (default "hermes").
#>
param([string]$Name = "hermes")
$ErrorActionPreference = 'Stop'

$hermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA 'hermes' }
if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    Write-Host "quick-launch: the 'hermes' command was not found. Install Hermes first."; exit 1
}
New-Item -ItemType Directory -Force -Path $hermesHome | Out-Null

# 1. launcher script (only rewritten when different; the old one is backed up)
$src = Join-Path $PSScriptRoot 'hermes-launch.vbs'
$dst = Join-Path $hermesHome 'hermes-launch.vbs'
if ((Test-Path $dst) -and ((Get-FileHash $dst).Hash -ne (Get-FileHash $src).Hash)) {
    Copy-Item $dst "$dst.bak-$(Get-Date -Format yyyyMMddHHmm)"
}
if (-not (Test-Path $dst) -or (Get-FileHash $dst).Hash -ne (Get-FileHash $src).Hash) {
    Copy-Item $src $dst -Force
    Write-Host "quick-launch: launcher written to $dst"
} else { Write-Host "quick-launch: launcher already up to date" }

# 2. Win+R name: HKCU App Paths\<name>.exe -> the launcher (per-user, no admin)
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\$Name.exe"
$cur = (Get-ItemProperty -Path $key -ErrorAction SilentlyContinue).'(default)'
if ($cur -eq $dst) {
    Write-Host "quick-launch: Win+R '$Name' already set"
} else {
    if ($cur) { Write-Host "quick-launch: Win+R '$Name' pointed to '$cur'; replacing it (to undo: uninstall.ps1)" }
    New-Item -Path $key -Force | Out-Null
    Set-ItemProperty -Path $key -Name '(default)' -Value $dst
    Write-Host "quick-launch: Win+R '$Name' now opens Hermes"
}

# 3. checks the user may need
$wt = @("$env:LOCALAPPDATA\Microsoft\WindowsApps\wt.exe", "$env:LOCALAPPDATA\WindowsTerminal\wt.exe") | Where-Object { Test-Path $_ }
if (-not $wt) { Write-Host "quick-launch: Windows Terminal not found; it will open in a plain PowerShell window (optional: winget install --id Microsoft.WindowsTerminal -e)" }
$pol = Get-ExecutionPolicy -Scope CurrentUser
if ($pol -in @('Restricted', 'AllSigned') -or ($pol -eq 'Undefined' -and (Get-ExecutionPolicy) -in @('Restricted', 'AllSigned'))) {
    Write-Host "quick-launch: note: PowerShell profiles are blocked (policy $pol). Only matters if you use a 'hermes' wrapper in your profile: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
}
Write-Host "quick-launch: done. Press Win+R, type '$Name', Enter."
