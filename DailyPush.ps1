# DailyPush.ps1 - Tech-Law Thailand scheduled push (12:30 PM)
# 1) CHECK data/{today}/content.json or Documents/รอบวันที่_{today}/
# 2) If missing, WAIT briefly for Claude noon pipeline, then continue
# 3) PUSH via PUSH.bat when there is today content or staged site changes
# 4) If no new law today and nothing to push → PASS SKIP (exit 0)
param(
    [switch]$Retry
)

$ErrorActionPreference = "Continue"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Repo

$LogDir = Join-Path $Repo "Logs"
if (-not (Test-Path -LiteralPath $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$Today = Get-Date -Format "yyyy-MM-dd"
$Log = Join-Path $LogDir ("tech-law-daily-{0}.log" -f $Today)
$DataContent = Join-Path $Repo ("data\{0}\content.json" -f $Today)
$DocRoundDir = Join-Path $Repo ("Documents\รอบวันที่_{0}" -f $Today)
$StatusLog = Join-Path $Repo "_บันทึกสถานะการตรวจสอบ.txt"
$PushBat = Join-Path $Repo "PUSH.bat"
$WaitAttempts = if ($Retry) { 40 } else { 20 }
$WaitSeconds = 30

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $Log -Value $line -Encoding UTF8
}

function Test-TodayContent {
    return (Test-Path -LiteralPath $DataContent) -or (Test-Path -LiteralPath $DocRoundDir)
}

function Test-HasUnpushedSiteChanges {
    Set-Location -LiteralPath $Repo
    $status = git status --porcelain -- "data/" "Documents/" "index.html" "js/" "assets/" ".nojekyll" 2>$null
    return -not [string]::IsNullOrWhiteSpace($status)
}

# Task Scheduler PATH / proxy hygiene
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\Git\bin;" +
    "$env:LOCALAPPDATA\Python\bin;$env:LOCALAPPDATA\Programs\Python\Python312;" +
    "$env:LOCALAPPDATA\Programs\Python\Python311;$env:LOCALAPPDATA\Programs\Python\Python310;" +
    $env:Path
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:ALL_PROXY = ""
$env:all_proxy = ""
$env:NO_PROXY = "*"
$env:no_proxy = "*"

Write-Log ("=== Tech-Law DailyPush.ps1 START (Retry={0}) ===" -f [bool]$Retry)
Write-Log ("Repo={0} Today={1}" -f $Repo, $Today)

if (-not (Test-Path -LiteralPath $PushBat)) {
    Write-Log ("ERROR: missing {0}" -f $PushBat)
    Write-Log "RESULT=FAIL"
    exit 1
}

Write-Log "[1/4] CHECK today content"
$hasToday = Test-TodayContent
$hasDirty = Test-HasUnpushedSiteChanges
Write-Log ("  data/{0}/content.json exists={1}" -f $Today, (Test-Path -LiteralPath $DataContent))
Write-Log ("  Documents/รอบวันที่_{0}/ exists={1}" -f $Today, (Test-Path -LiteralPath $DocRoundDir))
Write-Log ("  unpushed site changes={0}" -f $hasDirty)

if (-not $hasToday -and -not $hasDirty) {
    Write-Log "[2/4] WAIT for Claude noon pipeline / local publish"
    Write-Log ("  WAIT up to {0}x{1}s for data/Documents today" -f $WaitAttempts, $WaitSeconds)
    for ($i = 1; $i -le $WaitAttempts; $i++) {
        Start-Sleep -Seconds $WaitSeconds
        $hasToday = Test-TodayContent
        $hasDirty = Test-HasUnpushedSiteChanges
        Write-Log ("  wait {0}/{1}: todayContent={2} dirty={3}" -f $i, $WaitAttempts, $hasToday, $hasDirty)
        if ($hasToday -or $hasDirty) { break }
        if (Test-Path -LiteralPath $StatusLog) {
            $tail = Get-Content -LiteralPath $StatusLog -Tail 3 -ErrorAction SilentlyContinue
            if ($tail -match $Today -and $tail -match "ไม่พบกฎหมาย") {
                Write-Log "  status log says no new IT law today — skip push"
                Write-Log "RESULT=SKIP"
                Write-Log "=== Tech-Law DailyPush.ps1 END ==="
                exit 0
            }
        }
    }
}

$hasToday = Test-TodayContent
$hasDirty = Test-HasUnpushedSiteChanges

if (-not $hasToday -and -not $hasDirty) {
    Write-Log "No today content and no unpushed site changes — nothing to publish"
    Write-Log "RESULT=SKIP"
    Write-Log "=== Tech-Law DailyPush.ps1 END ==="
    exit 0
}

if ($hasToday) {
    try {
        if (Test-Path -LiteralPath $DataContent) {
            $payload = Get-Content -LiteralPath $DataContent -Raw -Encoding UTF8 | ConvertFrom-Json
            $n = @($payload.posts).Count
            Write-Log ("  Ready posts={0} date={1}" -f $n, $payload.date)
            if ($payload.date -and $payload.date -ne $Today) {
                Write-Log ("ERROR: content.date={0} is not TODAY={1}" -f $payload.date, $Today)
                Write-Log "RESULT=FAIL"
                exit 1
            }
            if ($n -lt 1) {
                Write-Log "ERROR: content.json has 0 posts"
                Write-Log "RESULT=FAIL"
                exit 1
            }
        } else {
            Write-Log ("  Documents round folder present without data/{0}/content.json yet — PUSH.bat will ingest if possible" -f $Today)
        }
    } catch {
        Write-Log ("ERROR: cannot parse content.json: {0}" -f $_)
        Write-Log "RESULT=FAIL"
        exit 1
    }
}

Write-Log "[3/4] PUSH via PUSH.bat"
$p = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "`"$PushBat`"") -WorkingDirectory $Repo -Wait -PassThru -NoNewWindow
Write-Log ("  PUSH.bat exit={0}" -f $p.ExitCode)
if ($p.ExitCode -ne 0) {
    Write-Log "ERROR: PUSH.bat failed"
    Write-Log "RESULT=FAIL"
    exit $p.ExitCode
}

Write-Log "[4/4] VERIFY git ahead=0"
Set-Location -LiteralPath $Repo
git fetch origin 2>$null | Out-Null
$ahead = 0
try { $ahead = [int](git rev-list --count "origin/main..HEAD" 2>$null) } catch { $ahead = -1 }
$head = (git rev-parse --short HEAD)
Write-Log ("  HEAD={0} AHEAD={1}" -f $head, $ahead)

if ($ahead -ne 0) {
    Write-Log ("ERROR: still ahead by {0}" -f $ahead)
    Write-Log "RESULT=FAIL"
    exit 1
}

Write-Log "RESULT=PASS"
Write-Log "SUCCESS https://chiraleo2000.github.io/tech-law-thailand/"
Write-Log "=== Tech-Law DailyPush.ps1 END ==="
exit 0
