# Re-register Tech-Law-DailyPush at 14:30 (2:30 PM) daily (same pattern as AI/Gov news)
# Push = newest/changed only. Local 180-day prune runs inside PUSH.bat (cloud untouched).
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "Tech-Law-DailyPush"
$Script = Join-Path $Repo "DailyPush.ps1"
$Sid = ([System.Security.Principal.WindowsIdentity]::GetCurrent()).User.Value

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Missing DailyPush.ps1 at $Script"
}

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Daily Tech-Law Thailand: push newest/changed only at 14:30; local prune &gt;180d after push (GitHub keeps full history)</Description>
    <URI>\Tech-Law-DailyPush</URI>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>$Sid</UserId>
      <LogonType>InteractiveToken</LogonType>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
  </Settings>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-10-22T14:30:00+07:00</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-NoProfile -ExecutionPolicy Bypass -File "$Script"</Arguments>
      <WorkingDirectory>$Repo</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = Join-Path $env:TEMP "Tech-Law-DailyPush.xml"
Set-Content -LiteralPath $xmlPath -Value $xml -Encoding Unicode
schtasks /Create /TN $TaskName /XML $xmlPath /F | Out-Host

$t = Get-ScheduledTask -TaskName $TaskName
$info = $t | Get-ScheduledTaskInfo
Write-Host ("Registered {0} State={1} NextRun={2}" -f $t.TaskName, $t.State, $info.NextRunTime)
