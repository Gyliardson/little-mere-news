@echo off
title Little Mere News - Installer
:: ============================================================================
:: Auto-Elevation: Requests Administrator privileges if not already running as Admin.
:: ============================================================================
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :admin
) else (
    echo [INFO] Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:admin
pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Install-LMN.ps1"
popd
