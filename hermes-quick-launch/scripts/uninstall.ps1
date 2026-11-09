<#
Hermes Quick Launch - uninstall. Removes the Win+R name and the launcher. Hermes itself is not touched.
  powershell -NoProfile -ExecutionPolicy Bypass -File uninstall.ps1 [-Name hermes]
#>
param([string]$Name = "hermes")
$hermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA 'hermes' }
$dst = Join-Path $hermesHome 'hermes-launch.vbs'
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\$Name.exe"
if ((Get-ItemProperty -Path $key -ErrorAction SilentlyContinue).'(default)' -eq $dst) {
    Remove-Item -Path $key -Force
    Write-Host "quick-launch: Win+R '$Name' removed"
} else { Write-Host "quick-launch: Win+R '$Name' was not set by quick-launch; left alone" }
if (Test-Path $dst) { Remove-Item $dst -Force; Write-Host "quick-launch: launcher removed" }
