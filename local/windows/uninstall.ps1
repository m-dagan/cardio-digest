Unregister-ScheduledTask -TaskName "Cardio Literature Digest" -Confirm:$false -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $env:LOCALAPPDATA "CardioDigest") -ErrorAction SilentlyContinue
Write-Host "Digest popup removed."
