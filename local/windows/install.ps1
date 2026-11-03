# Installs the Friday 4 pm digest popup on Windows.
#   usage (PowerShell):  powershell -ExecutionPolicy Bypass -File install.ps1 -Url https://<username>.github.io/<repo>/
param(
  [Parameter(Mandatory = $true)][string]$Url,
  [string]$Time = "4:00PM",
  [System.DayOfWeek]$Day = "Friday"
)
$ErrorActionPreference = "Stop"
$AppDir = Join-Path $env:LOCALAPPDATA "CardioDigest"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

$opener = @"
`$url = '$Url' + '?t=' + [DateTimeOffset]::Now.ToUnixTimeSeconds()
`$candidates = @(
  "`${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "`$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "`$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "`${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "`$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
`$browser = `$candidates | Where-Object { Test-Path `$_ } | Select-Object -First 1
if (`$browser) {
  Start-Process `$browser -ArgumentList "--app=`$url", "--window-size=640,900", "--window-position=60,60"
} else {
  Start-Process `$url
}
"@
$openerPath = Join-Path $AppDir "open-digest.ps1"
Set-Content -Path $openerPath -Value $opener -Encoding UTF8

$action   = New-ScheduledTaskAction -Execute "powershell.exe" `
            -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$openerPath`""
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Cardio Literature Digest" -Action $action -Trigger $trigger `
  -Settings $settings -Description "Opens the weekly literature digest" -Force | Out-Null

Write-Host "Installed. The digest will pop up every $Day at $Time (or as soon as the laptop is next on)."
Write-Host "Test now with:  powershell -ExecutionPolicy Bypass -File `"$openerPath`""
