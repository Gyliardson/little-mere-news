<#
.SYNOPSIS
Master orchestration script for the Little Mere News batch processing architecture.

.DESCRIPTION
Starts the required Hyper-V Virtual Machines, waits for the network to initialize,
runs the Harvester, transfers a durable inbound batch, runs the Publisher, and
shuts the VMs down. Every SSH/SCP boundary is checked explicitly so a failed
transfer or worker cannot be reported as a successful batch.
#>

function Stop-LmnCluster {
    param([string[]]$Names)
    Write-Host "      Shutting down VM cluster..." -ForegroundColor DarkGray
    Stop-VM -Name $Names -Force -ErrorAction SilentlyContinue
}

function Fail-LmnBatch {
    param(
        [string]$Message,
        [string[]]$VmNames
    )
    Write-Host "      [FATAL] $Message" -ForegroundColor Red
    Write-Host "      Recoverable queue files were not intentionally deleted." -ForegroundColor Yellow
    Stop-LmnCluster -Names $VmNames
    exit 1
}

function Invoke-CheckedExternal {
    param(
        [scriptblock]$Command,
        [string]$FailureMessage,
        [string[]]$VmNames
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Fail-LmnBatch -Message "$FailureMessage (exit $LASTEXITCODE)" -VmNames $VmNames
    }
}

$envFilePath = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFilePath) {
    Get-Content $envFilePath | Where-Object { $_ -match '=' -and $_ -notmatch '^#' } | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        Set-Item -Path "env:\$name" -Value $value.Trim()
    }
} else {
    Write-Host "[ERROR] .env file not found in the project root!" -ForegroundColor Red
    Write-Host "Copy .env.example to .env and insert the required server-side values." -ForegroundColor Yellow
    exit 1
}

$SUPABASE_URL = $env:SUPABASE_URL
$SUPABASE_KEY = $env:SUPABASE_KEY
if (-not $SUPABASE_URL -or -not $SUPABASE_KEY) {
    Write-Host "[ERROR] SUPABASE_URL and SUPABASE_KEY are required." -ForegroundColor Red
    exit 1
}

$VMs = "LMN-Harvester", "LMN-Brain", "LMN-Publisher"
$HarvesterHost = "lmnadmin@10.0.100.10"
$PublisherHost = "lmnadmin@10.0.100.30"
$HarvesterQueue = "/home/lmnadmin/news_to_publish.json"
$PublisherInbound = "/home/lmnadmin/news_to_publish.inbound.json"
$PublisherRetry = "/home/lmnadmin/news_to_publish.retry.json"
$PublisherRejected = "/home/lmnadmin/news_to_publish.rejected.json"
$HostTemp = Join-Path $PSScriptRoot "..\news_to_publish_temp.json"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " LMN BATCH PROCESSOR - INITIALIZING      " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

Write-Host "[1/5] Starting Virtual Machines ($VMs)..." -ForegroundColor Yellow
Start-VM -Name $VMs -ErrorAction SilentlyContinue

Write-Host "      Waiting for boot and network connection..." -ForegroundColor DarkGray
$IPs = "10.0.100.10", "10.0.100.20", "10.0.100.30"
foreach ($ip in $IPs) {
    while ($true) {
        if (Test-Connection -ComputerName $ip -Count 1 -Quiet) {
            Write-Host "      [+] VM $ip is online!" -ForegroundColor Green
            break
        }
        Start-Sleep -Seconds 2
    }
}
Write-Host "      Waiting for services (SSH, Ollama) to initialize (15s)..." -ForegroundColor DarkGray
Start-Sleep -Seconds 15

Write-Host "[2/5] Transferring Python logic to VMs..." -ForegroundColor Yellow
Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer feeds.json to Harvester" -Command {
    scp -o StrictHostKeyChecking=no ".\Backend-Harvester\feeds.json" "${HarvesterHost}:/home/lmnadmin/feeds.json" | Out-Null
}
Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Harvester code" -Command {
    scp -o StrictHostKeyChecking=no ".\Backend-Harvester\main.py" "${HarvesterHost}:/home/lmnadmin/main.py" | Out-Null
}
Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Publisher code" -Command {
    scp -o StrictHostKeyChecking=no ".\Backend-Publisher\main.py" "${PublisherHost}:/home/lmnadmin/main.py" | Out-Null
}

Write-Host "[3/5] Triggering LMN-Harvester (Data Collection & AI Processing)..." -ForegroundColor Yellow
Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Harvester failed; existing handoff remains recoverable" -Command {
    ssh -o StrictHostKeyChecking=no $HarvesterHost "/home/lmnadmin/harvester-env/bin/python /home/lmnadmin/main.py"
}
Write-Host "      Harvester completed and durable handoff state is ready." -ForegroundColor Green

Write-Host "[4/5] Bridging inbound data and triggering LMN-Publisher..." -ForegroundColor Yellow
Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue

# Pull the Harvester-owned pending batch. On failure the remote source remains untouched.
& scp -o StrictHostKeyChecking=no "${HarvesterHost}:$HarvesterQueue" $HostTemp 2>$null
if ($LASTEXITCODE -ne 0) {
    Fail-LmnBatch -Message "Could not pull Harvester handoff; remote batch retained" -VmNames $VMs
}

# Copy into Publisher-owned inbound path. This never overwrites Publisher-owned retry state.
& scp -o StrictHostKeyChecking=no $HostTemp "${PublisherHost}:$PublisherInbound" 2>$null
if ($LASTEXITCODE -ne 0) {
    Fail-LmnBatch -Message "Could not push Publisher inbound batch; Harvester source retained" -VmNames $VMs
}

Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue

# Only after the Publisher has a durable inbound copy may the Harvester relinquish its source batch.
Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Publisher inbound exists but Harvester source could not be cleared; next run will deduplicate safely" -Command {
    ssh -o StrictHostKeyChecking=no $HarvesterHost "rm -f '$HarvesterQueue'"
}

$publisherCommand = "export SUPABASE_URL='$SUPABASE_URL' && export SUPABASE_KEY='$SUPABASE_KEY' && export LMN_INPUT_FILE='$PublisherInbound' && export LMN_RETRY_FILE='$PublisherRetry' && export LMN_REJECTED_FILE='$PublisherRejected' && /home/lmnadmin/publisher-env/bin/python /home/lmnadmin/main.py"
& ssh -o StrictHostKeyChecking=no $PublisherHost $publisherCommand
$publisherExit = $LASTEXITCODE
if ($publisherExit -ne 0) {
    Write-Host "      [WARN] Publisher did not fully drain the queue (exit $publisherExit)." -ForegroundColor Yellow
    Write-Host "      Inbound/retry state is retained on the Publisher for the next run." -ForegroundColor Yellow
    Stop-LmnCluster -Names $VMs
    exit $publisherExit
}
Write-Host "      Publisher drained the current inbound/retry workload successfully." -ForegroundColor Green

Write-Host "[5/5] Shutting down VM cluster to conserve resources..." -ForegroundColor Yellow
Stop-LmnCluster -Names $VMs

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " BATCH COMPLETED! The web portal has been updated." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
exit 0
