<#
.SYNOPSIS
  run_daily.ps1 を毎日 9:00 に実行するタスクをタスクスケジューラに登録する（再実行すると上書き）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Time 08:30
  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Unregister
#>
param(
    [string]$Time = '09:00',
    [string]$TaskName = 'AI_NEWS_daily',
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "タスク '$TaskName' を削除しました"
    return
}

$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $PSScriptRoot 'run_daily.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory $Root

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# ログオン中のみ実行（claude のログイン情報を使うため。パスワードの保存は不要）
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'AIニュース収集パイプライン（①収集 → ②選定 → ③要約 → AI_NEWS.md 追記）' -Force | Out-Null

$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "タスク '$TaskName' を登録しました。次回実行: $($info.NextRunTime)"
