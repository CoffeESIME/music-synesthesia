#Requires -RunAsAdministrator
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 18743
)

$ErrorActionPreference = 'Stop'
$ruleName = "Proyecto-Sinestesia-LAN-$Port"
$existingRule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound `
        -Action Allow -Profile Private -RemoteAddress LocalSubnet `
        -Protocol TCP -LocalPort $Port | Out-Null
} else {
    New-NetFirewallRule -Name $ruleName `
        -DisplayName "Proyecto Sinestesia - red local TCP $Port" `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port `
        -RemoteAddress LocalSubnet -Profile Private | Out-Null
}
Write-Host "Puerto TCP $Port habilitado para la subred local en redes privadas."
