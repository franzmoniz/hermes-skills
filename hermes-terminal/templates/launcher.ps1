# Shared `hermes` launcher (Hermes's Skills). The same code is written by every skill that plugs into
# `hermes` (Hermes's Terminal, Hermes Device Sync...), so the order of the blocks does not matter.
# Each skill adds steps to $global:HermesHooks: 'before-*' (may set $global:HermesStop), one 'open-*'
# (how Hermes is opened), 'after-*'. Plain `hermes <args>` and `hermes-new` skip all of it.
if (-not $global:HermesHooks) { $global:HermesHooks = @{} }
function hermes {
    $exe = (Get-Command hermes -CommandType Application | Select-Object -First 1).Source
    if ($args.Count -gt 0) { & $exe @args; return }
    $global:HermesStop = $false
    $keys = @($global:HermesHooks.Keys | Sort-Object)
    foreach ($k in ($keys | Where-Object { $_ -like 'before-*' })) {
        & $global:HermesHooks[$k]
        if ($global:HermesStop) { exit }
    }
    $open = $keys | Where-Object { $_ -like 'open-*' } | Select-Object -First 1
    if ($open) { & $global:HermesHooks[$open] $exe } else { & $exe }
    foreach ($k in ($keys | Where-Object { $_ -like 'after-*' })) { & $global:HermesHooks[$k] }
}
function hermes-new {
    $exe = (Get-Command hermes -CommandType Application | Select-Object -First 1).Source
    & $exe @args
}
