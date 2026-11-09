<#
hermes-device-sync: enable the OpenSSH server on Windows so your OTHER devices can control this one.
Run in an ELEVATED PowerShell (Run as administrator). Safe to run again.

  .\windows-ssh-server.ps1 -AllowFrom 100.x.y.z,100.a.b.c [-AuthorizeKey "ssh-ed25519 AAAA... hermes-sync Laptop"]

-AllowFrom     extra addresses allowed to connect (your other devices' Tailscale IPs). The local
               home network (LocalSubnet) is always allowed; everything else is blocked.
-AuthorizeKey  a public key from devices/<device>.json ("ssh_pubkey") to authorize. Needed here
               when this Windows user is an administrator (OpenSSH then ignores ~/.ssh/authorized_keys).
#>
param([string[]]$AllowFrom = @(), [string]$AuthorizeKey = "")
$ErrorActionPreference = 'Stop'

$cap = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($cap.State -ne 'Installed') { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Set-Service sshd -StartupType Automatic
Start-Service sshd

# firewall: only the home network and your own devices
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH SSH Server (sshd)' -Enabled True `
        -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
}
Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -Profile Any -RemoteAddress (@('LocalSubnet') + $AllowFrom)

# PowerShell as the SSH shell is NOT required: remote.py sends powershell -EncodedCommand itself.

if ($AuthorizeKey) {
    $f = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
    if (-not (Test-Path $f) -or -not (Select-String -Path $f -SimpleMatch $AuthorizeKey -Quiet)) {
        Add-Content -Path $f -Value $AuthorizeKey -Encoding ascii
    }
    icacls $f /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null
}
Write-Host "sshd running. Allowed from: LocalSubnet $($AllowFrom -join ' ')"
