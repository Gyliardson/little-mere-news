@echo off
:: ============================================================================
:: Run-LMN.bat — Little Mere News Batch Launcher
:: Auto-elevates to Administrator and executes the PowerShell processing script.
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
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Run-LMN-Batch.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred while executing the batch script.
    pause
)
popd
