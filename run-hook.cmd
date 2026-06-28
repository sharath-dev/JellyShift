@echo off
setlocal EnableExtensions
REM ── Edit these three values for your WSL install ──────────────────────────
REM   wsl -l -v          → distro name
REM   wsl whoami           → username
REM   path to run-hook.sh  → where you cloned JellyShift inside WSL
set "WSL_DISTRO=Ubuntu-22.04"
set "WSL_USER=sharath"
set "HOOK_SH=/home/%WSL_USER%/projects/JellyShift/run-hook.sh"
REM ──────────────────────────────────────────────────────────────────────────
set "LOG=%TEMP%\jellyshift-hook.log"
>>"%LOG%" echo %DATE% %TIME% ─── Windows hook invoked ───
>>"%LOG%" echo   arg1=%~1
>>"%LOG%" echo   arg2=%~2
>>"%LOG%" echo   arg3=%~3
wsl.exe -d %WSL_DISTRO% -u %WSL_USER% -- %HOOK_SH% "%~1" "%~2" "%~3"
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo   wsl exit=%RC%
endlocal & exit /b %RC%
