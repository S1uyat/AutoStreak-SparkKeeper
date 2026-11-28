param(
  [ValidateSet('install','uninstall','status','plan')][string]$Action='status',
  [string]$ExecutablePath='',
  [string]$TaskName='SparkKeeper_OnceAtLogon',
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$Root = $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\pythonw.exe'
$Runner = Join-Path $Root 'runner.py'
try {
  if ($Action -eq 'install' -or $Action -eq 'plan') {
    if ($ExecutablePath) {
      $Py = (Resolve-Path -LiteralPath $ExecutablePath).Path
      $Root = [System.IO.Path]::GetDirectoryName($Py)
      $Arguments = '--run --scheduled'
    } else {
      if (-not (Test-Path -LiteralPath $Py)) { throw '找不到 Python 虚拟环境，请先安装。' }
      if (-not (Test-Path -LiteralPath $Runner)) { throw '找不到 runner.py。' }
      $Arguments = '"'+$Runner+'" --scheduled'
    }
    if ($DryRun) { $Arguments += ' --dry-run' }
    if ($Action -eq 'plan') {
      [ordered]@{Execute=$Py; Arguments=$Arguments; WorkingDirectory=$Root} | ConvertTo-Json -Compress
      exit 0
    }
    $Who = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $Act = New-ScheduledTaskAction -Execute $Py -Argument $Arguments -WorkingDirectory $Root
    $Trig = New-ScheduledTaskTrigger -AtLogOn -User $Who
    $Daily = New-ScheduledTaskTrigger -Daily -At '00:00'
    $Repeat = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 1)
    $Daily.Repetition = $Repeat.Repetition
    $Daily.Repetition.StopAtDurationEnd = $false
    # Start at logon without an additional scheduler delay.
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $Principal = New-ScheduledTaskPrincipal -UserId $Who -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $Act -Trigger @($Trig, $Daily) -Settings $Settings -Principal $Principal -Description '登录时及每天零点触发，每日去重；默认仅检查，由管理面板启用真实发送。完成后退出。' -Force | Out-Null
    Write-Output "安装完成：$TaskName"
    Write-Output '触发：登录及零点；每15分钟检查待补跑任务，发送前临时故障每天最多补跑2次；无常驻程序。'
  } elseif ($Action -eq 'uninstall') {
    $Found = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Found) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
    Write-Output '开机自动任务已取消；账号登录数据与配置仍保留在本机。'
  } else {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) { $Info = Get-ScheduledTaskInfo -TaskName $TaskName; Write-Output "已安装：$($Task.State)；下次检查：$($Info.NextRunTime)" }
    else { Write-Output '尚未安装开机自动任务' }
  }
  exit 0
} catch {
  Write-Error $_
  exit 1
}
