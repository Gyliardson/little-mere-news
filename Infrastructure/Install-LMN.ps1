<#
.SYNOPSIS
    Install-LMN.ps1
    Unified installer for the Little Mere News local infrastructure.

.DESCRIPTION
    This script orchestrates the full setup of the LMN platform:
      1. Runs the Hyper-V infrastructure provisioning (Setup-LMN-Infrastructure.ps1)
      2. Creates a Desktop shortcut for the Batch Processor with the project icon

    Designed to be a one-click experience for any new user of the project.

.PARAMETER DryRun
    Simulates Phase 1 (infrastructure) without making changes.
    Phase 2 (shortcut creation) still runs normally for verification.

.NOTES
    Project: Little Mere News - Bilingual tech news portal processed by local AI
    Requires: Windows 11 Pro/Enterprise, PowerShell 5.1+, Administrator Privileges
#>

#Requires -RunAsAdministrator

param(
    [switch]$DryRun
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$ErrorActionPreference = "Stop"
$InfrastructureDir = $PSScriptRoot
$ProjectRoot = Split-Path $InfrastructureDir -Parent

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Banner {
    Write-Host ""
    Write-Host "    ============================================================" -ForegroundColor Cyan
    Write-Host "    ||                                                        ||" -ForegroundColor Cyan
    Write-Host "    ||      LITTLE MERE NEWS - PLATFORM INSTALLER             ||" -ForegroundColor Cyan
    Write-Host "    ||      Bilingual Tech News - Powered by Local AI         ||" -ForegroundColor Cyan
    Write-Host "    ||                                                        ||" -ForegroundColor Cyan
    Write-Host "    ============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Title, [string]$Subtitle)
    Write-Host ""
    Write-Host "  ========================================================" -ForegroundColor DarkCyan
    Write-Host "  $Title" -ForegroundColor White
    if ($Subtitle) {
        Write-Host "  $Subtitle" -ForegroundColor DarkGray
    }
    Write-Host "  ========================================================" -ForegroundColor DarkCyan
    Write-Host ""
}

function Write-StepInfo {
    param([string]$Step, [string]$Message)
    Write-Host "  [$Step] $Message" -ForegroundColor Yellow
}

function Write-OK {
    param([string]$Message)
    Write-Host "  [OK]   $Message" -ForegroundColor Green
}

function Write-Skip {
    param([string]$Message)
    Write-Host "  [SKIP] $Message" -ForegroundColor DarkYellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

# ============================================================================
# PHASE 1: INFRASTRUCTURE PROVISIONING (Hyper-V, Network, VMs)
# ============================================================================

function Invoke-InfrastructureSetup {
    Write-Section "PHASE 1 OF 2: Infrastructure Provisioning" `
                  "Hyper-V activation, virtual network, ISO download, and VM creation."

    # --- DRY RUN MODE ---
    if ($DryRun) {
        Write-Host "  +---------------------------------------------+" -ForegroundColor Magenta
        Write-Host "  |  DRY RUN MODE - No changes will be made.    |" -ForegroundColor Magenta
        Write-Host "  +---------------------------------------------+" -ForegroundColor Magenta
        Write-Host ""
        Write-StepInfo "SIM" "Would enable Hyper-V (if not already active)."
        Start-Sleep -Milliseconds 400
        Write-StepInfo "SIM" "Would create Internal Virtual Switch 'LMN-Internal-Switch'."
        Start-Sleep -Milliseconds 400
        Write-StepInfo "SIM" "Would download Ubuntu Server 24.04 LTS ISO (~2.6 GB)."
        Start-Sleep -Milliseconds 400
        Write-StepInfo "SIM" "Would provision 3 Gen2 VMs: LMN-Harvester, LMN-Brain, LMN-Publisher."
        Start-Sleep -Milliseconds 400
        Write-Host ""
        Write-OK "Dry run simulation completed. No system changes were made."
        return $true
    }

    # --- REAL EXECUTION ---
    $setupScript = Join-Path $InfrastructureDir "Setup-LMN-Infrastructure.ps1"

    if (-not (Test-Path $setupScript)) {
        Write-Err "Setup-LMN-Infrastructure.ps1 not found at: $setupScript"
        Write-Host "  Skipping infrastructure provisioning." -ForegroundColor Yellow
        return $false
    }

    Write-StepInfo "1/2" "Launching infrastructure provisioning script..."
    Write-Host ""

    try {
        & $setupScript
        Write-Host ""
        Write-OK "Infrastructure provisioning completed."
        return $true
    }
    catch {
        Write-Host ""
        Write-Err "Infrastructure provisioning encountered an error: $($_.Exception.Message)"
        Write-Host ""

        $response = Read-Host "  Continue with shortcut creation anyway? (Y/N)"
        if ($response -eq 'Y' -or $response -eq 'y') {
            return $true
        }
        return $false
    }
}

# ============================================================================
# PHASE 2: DESKTOP SHORTCUT CREATION
# ============================================================================

function Install-DesktopShortcut {
    Write-Section "PHASE 2 OF 2: Desktop Shortcut" `
                  "Creating a launch shortcut with the project icon on your Desktop."

    # Paths
    $batchLauncher = Join-Path $InfrastructureDir "Run-LMN.bat"
    $iconPath      = Join-Path $ProjectRoot "frontend-web\public\favicon.ico"
    $desktopPath   = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
    $shortcutPath  = Join-Path $desktopPath "Little Mere News - Batch.lnk"

    # Validate launcher exists
    if (-not (Test-Path $batchLauncher)) {
        Write-Err "Run-LMN.bat not found at: $batchLauncher"
        Write-Host "  Cannot create shortcut without the batch launcher." -ForegroundColor Yellow
        return
    }

    # Check if shortcut already exists
    if (Test-Path $shortcutPath) {
        Write-Skip "Desktop shortcut already exists: $shortcutPath"
        $response = Read-Host "  Overwrite existing shortcut? (Y/N)"
        if ($response -ne 'Y' -and $response -ne 'y') {
            return
        }
    }

    # Create shortcut using WScript.Shell COM object
    Write-StepInfo "2/2" "Creating Desktop shortcut..."

    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($shortcutPath)
        $Shortcut.TargetPath       = $batchLauncher
        $Shortcut.WorkingDirectory = $InfrastructureDir
        $Shortcut.Description      = "Little Mere News - Run the batch processing pipeline"

        # Apply custom icon if available, otherwise use default
        if (Test-Path $iconPath) {
            $Shortcut.IconLocation = "$iconPath,0"
            Write-OK "Custom project icon applied."
        }
        else {
            Write-Skip "favicon.ico not found. Using default Windows icon."
        }

        $Shortcut.Save()
        Write-OK "Shortcut created: $shortcutPath"
    }
    catch {
        Write-Err "Failed to create shortcut: $($_.Exception.Message)"
    }
}

# ============================================================================
# FINAL SUMMARY
# ============================================================================

function Show-InstallSummary {
    $shortcutPath = Join-Path ([System.IO.Path]::Combine($env:USERPROFILE, "Desktop")) "Little Mere News - Batch.lnk"
    $shortcutExists = Test-Path $shortcutPath

    Write-Host ""
    Write-Host ""
    Write-Host "    ============================================================" -ForegroundColor Green
    Write-Host "    ||              INSTALLATION COMPLETE                      ||" -ForegroundColor Green
    Write-Host "    ============================================================" -ForegroundColor Green

    Write-Host ""
    Write-Host "  Summary:" -ForegroundColor White
    Write-Host "  -----------------------------------------" -ForegroundColor DarkGray

    if ($shortcutExists) {
        Write-Host "  [OK]   Desktop Shortcut  : Installed" -ForegroundColor Green
    }
    else {
        Write-Host "  [FAIL] Desktop Shortcut  : Not Created" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "  How to use:" -ForegroundColor Cyan
    Write-Host "  Double-click the 'Little Mere News - Batch' icon on your" -ForegroundColor White
    Write-Host "  Desktop to run the full news processing pipeline." -ForegroundColor White
    Write-Host "  Administrator privileges will be requested automatically." -ForegroundColor DarkGray
    Write-Host ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

Clear-Host
Write-Banner

if ($DryRun) {
    Write-Host "  [DRY RUN] Infrastructure will be simulated. No system changes." -ForegroundColor Magenta
    Write-Host ""    
}

# Phase 1: Infrastructure
$proceed = Invoke-InfrastructureSetup

if (-not $proceed) {
    Write-Host ""
    Write-Host "  Installation halted. Please resolve the above issues and try again." -ForegroundColor Yellow
    Write-Host ""
    Pause
    exit 0
}

# Phase 2: Shortcut
Install-DesktopShortcut

# Summary
Show-InstallSummary

Pause
