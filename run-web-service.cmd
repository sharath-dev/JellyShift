@echo off
setlocal EnableExtensions
REM Start JellyShift Web UI via systemd inside WSL (survives terminal close).
REM Edit WSL_DISTRO and WSL_USER to match your install (same as run-hook.cmd).

set "WSL_DISTRO=Ubuntu-22.04"
set "WSL_USER=sharath"

wsl.exe -d %WSL_DISTRO% -u %WSL_USER% -- systemctl --user start jellyshift-web.service
exit /b %ERRORLEVEL%
