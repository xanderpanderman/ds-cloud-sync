@echo off
setlocal enabledelayedexpansion

echo 🎮 DS2 Cloud Sync - Windows Installation
echo.

:: Check if PowerShell is available
powershell -Command "exit 0" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ PowerShell is required but not available
    echo Please install PowerShell or download the binary manually from:
    echo https://github.com/xanderpanderman/ds-cloud-sync/releases
    pause
    exit /b 1
)

:: Run the PowerShell installer
echo Running PowerShell installer...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" -AddToStartMenu -AddToDesktop

echo.
echo Installation complete! Check above for any errors.
pause