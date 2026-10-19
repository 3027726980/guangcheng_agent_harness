@echo off
setlocal EnableExtensions
if /I "%~1"=="--check" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Target All -Restart -CheckOnly
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Target All -Restart
)
set "HARNESS_EXIT=%ERRORLEVEL%"
if not "%HARNESS_EXIT%"=="0" if /I not "%~1"=="--check" pause
exit /b %HARNESS_EXIT%
