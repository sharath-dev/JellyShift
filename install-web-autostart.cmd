@echo off
setlocal EnableExtensions
REM Register a Windows logon task that starts the JellyShift Web UI in WSL.
REM Run once from an elevated Command Prompt if schtasks fails without admin.
REM Edit WSL_DISTRO and WSL_USER below.

set "WSL_DISTRO=Ubuntu-22.04"
set "WSL_USER=sharath"
set "TASK_NAME=JellyShift Web UI"
set "SCRIPT=%~dp0run-web-service.cmd"

schtasks /Create /TN "%TASK_NAME%" /TR "\"%SCRIPT%\"" /SC ONLOGON /RL LIMITED /F
if errorlevel 1 (
  echo Failed to create scheduled task. Try running as Administrator.
  exit /b 1
)

echo Scheduled task created: "%TASK_NAME%"
echo It will start the Web UI when you log in to Windows.
echo.
echo Also add this to %%USERPROFILE%%\.wslconfig so WSL stays running:
echo   [wsl2]
echo   vmIdleTimeout=-1
exit /b 0
