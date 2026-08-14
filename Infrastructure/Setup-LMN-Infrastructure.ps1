<#
.SYNOPSIS
    Setup-LMN-Infrastructure.ps1
    Automated Hyper-V infrastructure provisioning for the Little Mere News project.

.DESCRIPTION
    This script executes Phase 1 of the LMN project in two stages:
      Stage 1 - Enables Hyper-V (requires reboot)
      Stage 2 - Creates the internal virtual network and 3 Gen2 VMs with Ubuntu Server 24.04 LTS

    The script is idempotent: it can be safely re-executed after a reboot
    or in case of partial failure. Existing resources will be preserved.

.NOTES
    Project: Little Mere News - Bilingual tech news portal processed by local AI
    Requires: Windows 11 Pro/Enterprise, PowerShell 5.1+, Administrator Privileges
    Author: Generated via Antigravity for the LMN project
#>

#Requires -RunAsAdministrator

# ============================================================================
# CONFIGURATION
# ============================================================================

$ErrorActionPreference = "Stop"

# Base paths are derived from this script so the repository can live anywhere.
$InfraRoot     = $PSScriptRoot
$ProjectRoot   = Split-Path $InfraRoot -Parent
$VMStoragePath = Join-Path $InfraRoot "VMs"
$ISOPath       = Join-Path $InfraRoot "ISO"

# Network configuration
$SwitchName = "LMN-Internal-Switch"

# Ubuntu Server 24.04 LTS ISO. Keep the default explicit and review it when
# Canonical advances the 24.04 point release; callers may override without source edits.
$ISOUrl = if ($env:LMN_UBUNTU_ISO_URL) {
    $env:LMN_UBUNTU_ISO_URL.Trim()
} else {
    "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso"
}
$ISOFileName = "ubuntu-24.04-live-server-amd64.iso"
$ISOFullPath = Join-Path $ISOPath $ISOFileName
$ExpectedISOSha256 = if ($env:LMN_UBUNTU_ISO_SHA256) {
    $env:LMN_UBUNTU_ISO_SHA256.Trim().ToLowerInvariant()
} else {
    ""
}

# VM Definitions
$VMDefinitions = @(
    @{
        Name       = "LMN-Harvester"
        MemoryMB   = 2048        # 2 GB
        VCPUs      = 2
        DiskSizeGB = 30
        Role       = "Data collection via RSS/APIs"
    },
    @{
        Name       = "LMN-Brain"
        MemoryMB   = 8192        # 8 GB (minimum for local AI)
        VCPUs      = 4
        DiskSizeGB = 30
        Role       = "Local AI inference (Ollama)"
    },
    @{
        Name       = "LMN-Publisher"
        MemoryMB   = 2048        # 2 GB
        VCPUs      = 2
        DiskSizeGB = 30
        Role       = "Database client and publisher"
    }
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Message)
    $separator = "=" * 72
    Write-Host ""
    Write-Host $separator -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host $separator -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "  [*] $Message" -ForegroundColor White
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Skip {
    param([string]$Message)
    Write-Host "  [SKIP] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Confirm-Action {
    param([string]$Prompt)
    $response = Read-Host "$Prompt (Y/N)"
    return ($response -eq 'Y' -or $response -eq 'y' -or $response -eq 'Yes' -or $response -eq 'yes')
}

function Assert-LmnIsoDigestConfiguration {
    if ($ExpectedISOSha256 -notmatch '^[0-9a-f]{64}$') {
        Write-Fail "LMN_UBUNTU_ISO_SHA256 must contain the trusted 64-character SHA-256 digest for the configured Ubuntu ISO."
        Write-Host "  Obtain the digest from Ubuntu's official release manifest through a trusted channel, set the environment variable, and retry." -ForegroundColor Yellow
        Write-Host "  A SHA-256 digest verifies image integrity; it is not an independent signature of the release origin." -ForegroundColor DarkGray
        exit 1
    }

    $parsedIsoUri = $null
    if (-not [Uri]::TryCreate($ISOUrl, [UriKind]::Absolute, [ref]$parsedIsoUri) -or $parsedIsoUri.Scheme -ne "https") {
        Write-Fail "LMN_UBUNTU_ISO_URL must be an absolute HTTPS URL."
        exit 1
    }
}

function Assert-LmnIsoIntegrity {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Write-Fail "ISO file was not found for integrity verification: $Path"
        exit 1
    }

    $actualDigest = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualDigest -ne $ExpectedISOSha256) {
        Write-Fail "Ubuntu ISO SHA-256 mismatch. Refusing to use unverified boot media."
        Write-Host "  Expected: $ExpectedISOSha256" -ForegroundColor DarkGray
        Write-Host "  Actual:   $actualDigest" -ForegroundColor DarkGray
        exit 1
    }

    Write-Success "Ubuntu ISO SHA-256 verified."
}

# ============================================================================
# STAGE 1: HYPER-V VERIFICATION AND ACTIVATION
# ============================================================================

function Invoke-HyperVSetup {
    Write-Header "STAGE 1: Hyper-V Verification"

    $hyperv = Get-WindowsOptionalFeature -Online -FeatureName "Microsoft-Hyper-V" -ErrorAction SilentlyContinue

    if ($null -eq $hyperv) {
        Write-Fail "Could not query Hyper-V status."
        Write-Fail "Ensure you are using Windows 11 Pro or Enterprise."
        exit 1
    }

    if ($hyperv.State -eq "Enabled") {
        Write-Success "Hyper-V is already enabled on this system."
        return $true  # Proceed to Stage 2
    }

    # Hyper-V is not enabled - activate it now
    Write-Step "Hyper-V is disabled. Initiating activation..."
    Write-Host ""

    try {
        Enable-WindowsOptionalFeature -Online -FeatureName "Microsoft-Hyper-V" -All -NoRestart | Out-Null
        Write-Success "Hyper-V activated successfully."
    }
    catch {
        Write-Fail "Failed to activate Hyper-V: $($_.Exception.Message)"
        exit 1
    }

    # Request reboot
    Write-Host ""
    Write-Host "  -------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "  MANDATORY REBOOT REQUIRED" -ForegroundColor Yellow
    Write-Host "  -------------------------------------------------------" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Hyper-V has been enabled, but Windows must be" -ForegroundColor White
    Write-Host "  rebooted to finalize the installation." -ForegroundColor White
    Write-Host ""
    Write-Host "  After rebooting, re-execute this script to" -ForegroundColor White
    Write-Host "  proceed with Stage 2 (Network & VM provisioning)." -ForegroundColor White
    Write-Host ""

    if (Confirm-Action "  Do you wish to reboot the computer NOW?") {
        Write-Step "Rebooting in 5 seconds..."
        Start-Sleep -Seconds 5
        Restart-Computer -Force
    }
    else {
        Write-Host ""
        Write-Host "  Reboot deferred. Please remember:" -ForegroundColor Yellow
        Write-Host "  1. Reboot the computer manually." -ForegroundColor White
        Write-Host "  2. Re-execute this script as Administrator." -ForegroundColor White
        Write-Host ""
    }

    return $false  # Cannot proceed without reboot
}

# ============================================================================
# STAGE 2: NETWORK CONFIGURATION
# ============================================================================

function Invoke-NetworkSetup {
    Write-Header "STAGE 2A: Virtual Network Configuration"

    $existingSwitch = Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue

    if ($null -ne $existingSwitch) {
        Write-Skip "Virtual Switch '$SwitchName' already exists (Type: $($existingSwitch.SwitchType))."
        return
    }

    Write-Step "Creating Internal Virtual Switch '$SwitchName'..."

    try {
        New-VMSwitch -Name $SwitchName -SwitchType Internal | Out-Null
        Write-Success "Virtual Switch '$SwitchName' successfully created."
    }
    catch {
        Write-Fail "Failed to create Virtual Switch: $($_.Exception.Message)"
        exit 1
    }

    # Display network adapter info
    $adapter = Get-NetAdapter | Where-Object { $_.Name -like "*$SwitchName*" }
    if ($adapter) {
        Write-Step "Associated network adapter: $($adapter.Name) (Status: $($adapter.Status))"
        Write-Host ""
        Write-Host "  NOTE: For Host <-> VM communication, you may configure a static" -ForegroundColor DarkGray
        Write-Host "  IP address on this adapter. Example:" -ForegroundColor DarkGray
        Write-Host "  New-NetIPAddress -InterfaceAlias '$($adapter.Name)' -IPAddress 10.0.100.1 -PrefixLength 24" -ForegroundColor DarkGray
    }
}

# ============================================================================
# STAGE 2: ISO DOWNLOAD
# ============================================================================

function Invoke-ISODownload {
    Write-Header "STAGE 2B: Ubuntu Server 24.04 LTS ISO"
    Assert-LmnIsoDigestConfiguration

    # Create ISO directory if missing
    if (-not (Test-Path $ISOPath)) {
        New-Item -Path $ISOPath -ItemType Directory -Force | Out-Null
        Write-Step "ISO directory created: $ISOPath"
    }

    # Existing media is reusable only after cryptographic integrity verification.
    if (Test-Path -LiteralPath $ISOFullPath -PathType Leaf) {
        $fileSize = (Get-Item $ISOFullPath).Length
        $fileSizeGB = [math]::Round($fileSize / 1GB, 2)
        Write-Skip "ISO already exists: $ISOFullPath ($fileSizeGB GB)"
        Assert-LmnIsoIntegrity -Path $ISOFullPath
        return
    }

    Write-Step "Initiating Ubuntu Server 24.04 LTS ISO download..."
    Write-Host "  URL: $ISOUrl" -ForegroundColor DarkGray
    Write-Host "  Target: $ISOFullPath" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Download may take several minutes depending on network bandwidth." -ForegroundColor DarkGray
    Write-Host ""

    try {
        # Prefer BITS for large downloads
        $bitsSupport = Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue

        if ($bitsSupport) {
            Write-Step "Using BITS (Background Intelligent Transfer Service)..."
            Start-BitsTransfer -Source $ISOUrl -Destination $ISOFullPath -DisplayName "Ubuntu Server 24.04 LTS Download" -Description "Little Mere News ISO"
        }
        else {
            Write-Step "Using Invoke-WebRequest..."
            $ProgressPreference = 'Continue'
            Invoke-WebRequest -Uri $ISOUrl -OutFile $ISOFullPath -UseBasicParsing
        }

        Assert-LmnIsoIntegrity -Path $ISOFullPath
        $downloadedSize = (Get-Item $ISOFullPath).Length
        $downloadedSizeGB = [math]::Round($downloadedSize / 1GB, 2)
        Write-Success "Download complete and verified: $ISOFullPath ($downloadedSizeGB GB)"
    }
    catch {
        Remove-Item $ISOFullPath -Force -ErrorAction SilentlyContinue
        Write-Fail "ISO download or verification failed: $($_.Exception.Message)"
        Write-Host ""
        Write-Host "  Manual recovery:" -ForegroundColor Yellow
        Write-Host "  1. Download the exact configured Ubuntu ISO through a trusted channel." -ForegroundColor White
        Write-Host "  2. Verify its SHA-256 against Ubuntu's official release manifest." -ForegroundColor White
        Write-Host "  3. Save it to: $ISOFullPath" -ForegroundColor White
        Write-Host "  4. Set LMN_UBUNTU_ISO_SHA256 to that trusted digest and re-execute this script." -ForegroundColor White
        Write-Host ""
        exit 1
    }
}

# ============================================================================
# STAGE 2: VM PROVISIONING
# ============================================================================

function New-LMNVM {
    param(
        [hashtable]$VMDef
    )

    $vmName     = $VMDef.Name
    $memoryBytes = [int64]$VMDef.MemoryMB * 1MB
    $diskSizeBytes = [int64]$VMDef.DiskSizeGB * 1GB
    $vcpus      = $VMDef.VCPUs
    $role       = $VMDef.Role

    Write-Host ""
    Write-Host "  --- $vmName ---" -ForegroundColor Cyan
    Write-Host "  Role: $role" -ForegroundColor DarkGray
    Write-Host "  RAM: $($VMDef.MemoryMB) MB | Disk: $($VMDef.DiskSizeGB) GB | vCPUs: $vcpus" -ForegroundColor DarkGray

    # Check if VM exists
    $existingVM = Get-VM -Name $vmName -ErrorAction SilentlyContinue
    if ($null -ne $existingVM) {
        Write-Skip "VM '$vmName' already exists (State: $($existingVM.State))."
        return
    }

    # Prepare directories
    $vmFolder   = Join-Path $VMStoragePath $vmName
    $vhdxPath   = Join-Path $vmFolder "$vmName.vhdx"

    if (-not (Test-Path $vmFolder)) {
        New-Item -Path $vmFolder -ItemType Directory -Force | Out-Null
    }

    # 1. Create VHDX Drive
    if (-not (Test-Path $vhdxPath)) {
        Write-Step "Creating Dynamic VHDX ($($VMDef.DiskSizeGB) GB)..."
        New-VHD -Path $vhdxPath -SizeBytes $diskSizeBytes -Dynamic | Out-Null
        Write-Success "VHDX created: $vhdxPath"
    }
    else {
        Write-Skip "VHDX already exists: $vhdxPath"
    }

    # 2. Create Gen2 VM
    Write-Step "Provisioning Generation 2 VM..."
    $newVM = New-VM `
        -Name $vmName `
        -Generation 2 `
        -MemoryStartupBytes $memoryBytes `
        -VHDPath $vhdxPath `
        -SwitchName $SwitchName `
        -Path $vmFolder

    Write-Success "VM '$vmName' successfully created."

    # 3. Configure Processors
    Write-Step "Assigning $vcpus vCPUs..."
    Set-VMProcessor -VMName $vmName -Count $vcpus

    # 4. Disable Dynamic Memory (for performance predictability)
    Write-Step "Disabling dynamic memory allocation..."
    Set-VMMemory -VMName $vmName -DynamicMemoryEnabled $false

    # 5. Configure Secure Boot for Linux
    Write-Step "Configuring Secure Boot Template (MicrosoftUEFICertificateAuthority)..."
    Set-VMFirmware -VMName $vmName -SecureBootTemplate "MicrosoftUEFICertificateAuthority"

    # 6. Disable automatic checkpoints (recommended for production)
    Write-Step "Disabling automatic checkpoints..."
    Set-VM -VMName $vmName -AutomaticCheckpointsEnabled $false

    # 7. Mount ISO if available
    if (Test-Path $ISOFullPath) {
        Write-Step "Mounting Installation ISO..."

        # Add DVD Drive
        Add-VMDvdDrive -VMName $vmName

        # Get the newly created DVD drive
        $dvdDrive = Get-VMDvdDrive -VMName $vmName | Select-Object -First 1

        # Insert ISO
        Set-VMDvdDrive -VMName $vmName `
            -ControllerNumber $dvdDrive.ControllerNumber `
            -ControllerLocation $dvdDrive.ControllerLocation `
            -Path $ISOFullPath

        # Set boot order: DVD first, then HDD
        $bootDVD  = Get-VMDvdDrive -VMName $vmName | Select-Object -First 1
        $bootHD   = Get-VMHardDiskDrive -VMName $vmName | Select-Object -First 1
        Set-VMFirmware -VMName $vmName -BootOrder $bootDVD, $bootHD

        Write-Success "ISO mounted and boot order updated (DVD > HDD)."
    }
    else {
        Write-Host "  [WARNING] ISO not found. VM created without boot media." -ForegroundColor Yellow
        Write-Host "  Mount the ISO manually later: $ISOFullPath" -ForegroundColor DarkGray
    }

    Write-Success "VM '$vmName' fully provisioned."
}

function Invoke-VMProvisioning {
    Write-Header "STAGE 2C: Virtual Machine Provisioning"

    # Create VM storage directory if missing
    if (-not (Test-Path $VMStoragePath)) {
        New-Item -Path $VMStoragePath -ItemType Directory -Force | Out-Null
        Write-Step "VM storage directory created: $VMStoragePath"
    }

    # Provision VMs
    foreach ($vmDef in $VMDefinitions) {
        try {
            New-LMNVM -VMDef $vmDef
        }
        catch {
            Write-Fail "Failed to provision '$($vmDef.Name)': $($_.Exception.Message)"
            Write-Host "  Proceeding with remaining VMs..." -ForegroundColor Yellow
        }
    }
}

# ============================================================================
# FINAL REPORT
# ============================================================================

function Show-FinalReport {
    Write-Header "FINAL REPORT"

    # Hyper-V Status
    $hvStatus = (Get-WindowsOptionalFeature -Online -FeatureName "Microsoft-Hyper-V").State
    Write-Host "  Hyper-V: $hvStatus" -ForegroundColor White

    # Switch Status
    $sw = Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue
    if ($sw) {
        Write-Host "  Virtual Switch: $SwitchName (Type: $($sw.SwitchType))" -ForegroundColor White
    }
    else {
        Write-Host "  Virtual Switch: NOT FOUND" -ForegroundColor Red
    }

    # ISO Status
    if (Test-Path $ISOFullPath) {
        $isoSize = [math]::Round((Get-Item $ISOFullPath).Length / 1GB, 2)
        Write-Host "  ISO Media: $ISOFileName ($isoSize GB)" -ForegroundColor White
    }
    else {
        Write-Host "  ISO Media: NOT FOUND" -ForegroundColor Red
    }

    # VMs Status
    Write-Host ""
    Write-Host "  Provisioned Virtual Machines:" -ForegroundColor White
    $tableHeader = ("  {0,-20} {1,-12} {2,-10} {3,-8} {4}" -f "NAME", "STATE", "RAM (MB)", "vCPUs", "DISK")
    Write-Host $tableHeader -ForegroundColor DarkGray
    $tableSeparator = "  " + ("-" * 68)
    Write-Host $tableSeparator -ForegroundColor DarkGray

    foreach ($vmDef in $VMDefinitions) {
        $vm = Get-VM -Name $vmDef.Name -ErrorAction SilentlyContinue
        if ($vm) {
            $ramMB = [math]::Round($vm.MemoryStartup / 1MB)
            $cpus  = $vm.ProcessorCount
            $vhdx  = Join-Path (Join-Path $VMStoragePath $vmDef.Name) "$($vmDef.Name).vhdx"
            $diskExists = if (Test-Path $vhdx) { "OK" } else { "MISSING" }

            $line = "  {0,-20} {1,-12} {2,-10} {3,-8} {4}" -f $vmDef.Name, $vm.State, $ramMB, $cpus, $diskExists
            Write-Host $line -ForegroundColor White
        }
        else {
            $line = "  {0,-20} {1,-12}" -f $vmDef.Name, "NOT CREATED"
            Write-Host $line -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "  Next Steps:" -ForegroundColor Cyan
    Write-Host "  1. Boot each VM and install Ubuntu Server 24.04 LTS." -ForegroundColor White
    Write-Host "  2. Configure static IP addresses on the $SwitchName subnet." -ForegroundColor White
    Write-Host "  3. Enroll verified SSH host keys and configure passwordless administrative access." -ForegroundColor White
    Write-Host "  4. Run .\Infrastructure\Bootstrap-LMN-Guests.ps1 from this reviewed checkout." -ForegroundColor White
    Write-Host "     That path transfers the canonical Python requirements and bounded Ollama setup." -ForegroundColor DarkGray
    Write-Host ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

Write-Host ""
Write-Host "  Little Mere News - Infrastructure Setup" -ForegroundColor Cyan
Write-Host "  Automated provisioning for local AI tech news platform" -ForegroundColor DarkGray
Write-Host ""

# Stage 1: Hyper-V Check
$canProceed = Invoke-HyperVSetup

if (-not $canProceed) {
    Write-Host "  Script terminated. Please re-execute after rebooting." -ForegroundColor Yellow
    exit 0
}

# Validate trusted ISO configuration before mutating Stage 2 network/VM state.
Assert-LmnIsoDigestConfiguration

# Stage 2: Network, ISO, and VM Provisioning
Invoke-NetworkSetup
Invoke-ISODownload
Invoke-VMProvisioning

# Report
Show-FinalReport

Write-Host "  Infrastructure provisioning completed successfully."
Write-Host ""