@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM === Daily Tech-Law Pages push (scheduled 12:30 PM) ===
REM Task Scheduler often has a thin PATH / inherited proxy — fix that first.
set "PATH=C:\Program Files\Git\cmd;C:\Program Files\Git\bin;%LOCALAPPDATA%\Python\bin;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python310;%PATH%"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="
set "NO_PROXY=*"
set "no_proxy=*"
set "GIT_HTTP_LOW_SPEED_LIMIT=1000"
set "GIT_HTTP_LOW_SPEED_TIME=60"

set "REPO=%CD%"
set "LOGDIR=%REPO%\Logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%I"
set "LOG=%LOGDIR%\tech-law-push-%TODAY%.log"
set "CLEAN_REMOTE=https://github.com/chiraleo2000/tech-law-thailand.git"
set "USED_PAT=0"
set "RESULT=FAIL"
set "BRANCH=main"
set "PAGES_URL=https://chiraleo2000.github.io/tech-law-thailand/"

call :log "=== Tech-Law Thailand PUSH ==="
call :log "Repo: %REPO%"
call :log "Time: %DATE% %TIME%"
call :pscheck "START" "Tech-Law PUSH starting"

where git >nul 2>&1
if errorlevel 1 ( set "ERR=git not found on PATH" & goto :fail )

where python >nul 2>&1
if errorlevel 1 ( set "ERR=python not found on PATH" & goto :fail )

if not exist ".git" ( set "ERR=not a git repo: %REPO%" & goto :fail )

set "HELPER=%~dp0update-manifest.py"
if not exist "%HELPER%" ( set "ERR=missing update-manifest.py" & goto :fail )

set "INGESTOR=%~dp0ingestor.py"

echo.
echo [0/7] Prepare today content paths
set "TARGET=%TODAY%"
set "DATA_DIR=data\!TARGET!"
set "CONTENT=!DATA_DIR!\content.json"
set "MANIFEST=data\manifest.json"

call :resolve_doc_round
call :log "Target date: !TARGET!"
call :log "Content: !CONTENT!"
call :log "Documents round: !DOC_ROUND!"
call :pscheck "SOURCE" "Checking !TARGET!"

REM If Documents round exists but data/content.json missing, try ingest
if exist "!DOC_ROUND!" if not exist "!CONTENT!" (
  if exist "%INGESTOR%" (
    call :log "Running ingestor.py for Documents round"
    call :pscheck "INGEST" "ingestor.py --date-dir"
    python "%INGESTOR%" --date-dir "!DOC_ROUND!"
    if errorlevel 1 ( set "ERR=ingestor.py failed" & goto :fail )
  )
)

if exist "!CONTENT!" (
  call :log "Found !CONTENT!"
  python "%HELPER%" --manifest "%MANIFEST%" --content "!CONTENT!"
  if errorlevel 1 ( set "ERR=manifest update failed" & goto :fail )
  call :pscheck "MANIFEST" "updated for !TARGET!"
) else (
  call :log "No today content.json — will push only if other site files changed"
)

echo.
echo [1/7] Clear .git locks
call :clear_locks
git remote set-url origin "%CLEAN_REMOTE%" 2>nul
call :pscheck "LOCKS" "Cleared"

if exist ".github-pat" (
  for /f "usebackq delims=" %%P in (".github-pat") do set "PAT=%%P"
  if defined PAT (
    git remote set-url origin "https://!PAT!@github.com/chiraleo2000/tech-law-thailand.git"
    set "USED_PAT=1"
    call :log "Using temporary PAT remote for push"
  )
)

echo.
echo [2/7] git add site paths
git add -- "data/" "Documents/" "index.html" "js/" "assets/" ".nojekyll" "_ประวัติกฎหมายที่ประมวลผลแล้ว.json" "_บันทึกสถานะการตรวจสอบ.txt" 2>nul
REM never stage secrets / schedule helpers accidentally as "news cleanup"
git reset HEAD -- ".github-pat" "Logs/" 2>nul
call :log "Staged files:"
for /f "delims=" %%F in ('git diff --cached --name-only') do call :log "  %%F"
call :pscheck "ADD" "Staged site paths"

echo.
echo [3/7] git commit
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Update tech law !TARGET!"
  if errorlevel 1 ( set "ERR=git commit failed" & goto :fail )
  call :log "Committed Update tech law !TARGET!"
  call :pscheck "COMMIT" "Update tech law !TARGET!"
) else (
  call :log "Nothing new to commit"
  call :pscheck "COMMIT" "Nothing new"
)

echo.
echo [4/7] Ensure local main is not behind before push
git fetch origin
if errorlevel 1 ( set "ERR=git fetch failed" & goto :fail )

echo.
echo [5/7] git push origin %BRANCH%
set "PUSHED=0"
git push origin HEAD:%BRANCH%
if not errorlevel 1 set "PUSHED=1"

if "!PUSHED!"=="0" (
  call :log "Push rejected - pull --rebase then retry"
  call :pscheck "RETRY" "pull --rebase"
  call :clear_locks
  git pull --rebase origin %BRANCH%
  if errorlevel 1 (
    call :log "rebase failed - abort and retry pull"
    git rebase --abort 2>nul
    git pull origin %BRANCH% --no-edit -X theirs
  )
  git push origin HEAD:%BRANCH%
  if errorlevel 1 (
    call :log "second push failed - one more pull --rebase"
    call :clear_locks
    git pull --rebase origin %BRANCH%
    git push origin HEAD:%BRANCH%
    if errorlevel 1 ( set "ERR=git push failed after retries" & goto :fail )
  )
)
call :log "Push OK"
call :pscheck "PUSH" "origin/%BRANCH% updated"

if "!USED_PAT!"=="1" (
  git remote set-url origin "%CLEAN_REMOTE%"
  call :log "Restored clean remote URL"
)

echo.
echo [6/7] Verify ahead=0
git fetch origin
if errorlevel 1 ( set "ERR=git fetch failed after push" & goto :fail )

for /f %%A in ('git rev-list --count origin/%BRANCH%..HEAD') do set "AHEAD=%%A"
call :log "AHEAD=!AHEAD!"
if not "!AHEAD!"=="0" ( set "ERR=still ahead by !AHEAD! commit(s) - PUSH FAIL" & goto :fail )

echo.
echo [7/7] Done
for /f %%H in ('git rev-parse --short HEAD') do set "HEADSHORT=%%H"
call :log "HEAD=!HEADSHORT!"
call :log "RESULT=PASS"
call :log "SUCCESS - %PAGES_URL%"
set "RESULT=PASS"
call :print_summary
echo.
echo ===== PUSH PASS =====
echo SUCCESS - %PAGES_URL%
exit /b 0

:resolve_doc_round
set "DOC_ROUND="
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$p=Join-Path '%REPO%' ('Documents\รอบวันที่_{0}' -f '%TODAY%'); if(Test-Path -LiteralPath $p){$p}"`) do set "DOC_ROUND=%%D"
exit /b 0

:clear_locks
del /f /q ".git\index.lock" 2>nul
del /f /q ".git\HEAD.lock" 2>nul
del /f /q ".git\config.lock" 2>nul
del /f /q ".git\refs\heads\main.lock" 2>nul
del /f /q ".git\shallow.lock" 2>nul
for /r ".git" %%F in (*.lock) do del /f /q "%%F" 2>nul
exit /b 0

:pscheck
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$step='%~1'; $msg='%~2'; $c='Cyan'; if($step -eq 'PUSH' -or $step -eq 'PASS'){$c='Green'}; if($step -eq 'FAIL'){$c='Red'}; Write-Host ('[{0}] {1}' -f $step,$msg) -ForegroundColor $c"
>>"%LOG%" echo %DATE% %TIME% [%~1] %~2
exit /b 0

:log
echo %~1
>>"%LOG%" echo %DATE% %TIME% %~1
exit /b 0

:print_summary
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$log='%LOG%'; $repo='%REPO%'; $result='%RESULT%'; $url='%PAGES_URL%'; Write-Host ''; Write-Host '==== Tech-Law Push Log (tail) ====' -ForegroundColor Cyan; if(Test-Path -LiteralPath $log){ Get-Content -LiteralPath $log -Tail 40 } else { Write-Host 'No log file' -ForegroundColor Yellow }; Write-Host ''; Set-Location -LiteralPath $repo; git fetch origin 2>$null | Out-Null; $ahead=0; try { $ahead=[int](git rev-list --count origin/main..HEAD 2>$null) } catch {}; $head=(git rev-parse --short HEAD); $orig=(git rev-parse --short origin/main 2>$null); Write-Host ('HEAD=' + $head + '  origin/main=' + $orig + '  AHEAD=' + $ahead); if($result -eq 'PASS' -and $ahead -eq 0){ Write-Host 'PUSH PASS' -ForegroundColor Green } else { Write-Host 'PUSH FAIL' -ForegroundColor Red }; Write-Host ('Live: ' + $url); Write-Host ('Log: ' + $log)"
exit /b 0

:fail
if "!USED_PAT!"=="1" git remote set-url origin "%CLEAN_REMOTE%" 2>nul
call :log "ERROR: !ERR!"
call :log "RESULT=FAIL"
set "RESULT=FAIL"
call :pscheck "FAIL" "!ERR!"
call :print_summary
echo.
echo ===== PUSH FAIL =====
echo ERROR: !ERR!
echo See log: %LOG%
exit /b 1
