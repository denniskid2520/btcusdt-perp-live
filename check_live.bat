@echo off
REM Double-click to pull latest telemetry snapshot and print the health report.
REM Runs tools/telemetry/check.sh via Git Bash.

cd /d "%~dp0"

REM Try bash on PATH first, then fall back to common Git for Windows locations.
where bash >nul 2>&1
if %errorlevel% == 0 (
    bash tools/telemetry/check.sh %*
) else if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" tools/telemetry/check.sh %*
) else if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    "C:\Program Files (x86)\Git\bin\bash.exe" tools/telemetry/check.sh %*
) else (
    echo [ERROR] Git Bash not found.
    echo Install Git for Windows: https://git-scm.com/download/win
)

echo.
echo ============================================================
echo Press any key to close this window...
pause >nul
