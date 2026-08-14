<#
.SYNOPSIS
Master orchestration script for the Little Mere News batch processing architecture.

.DESCRIPTION
Starts the required Hyper-V Virtual Machines, serializes batch executions, drains
any retained Publisher state before harvesting new work, transfers a durable inbound
batch, and propagates every SSH/SCP/worker failure instead of reporting false success.
Remote host identity is verified against a pre-enrolled known_hosts file, and
Publisher secrets remain provisioned on the Publisher VM rather than being sent in
SSH command arguments. Repository-local worker sources are resolved from this script's
location and never from the caller's current working directory.
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

function Wait-LmnVmNetwork {
    param(
        [string]$IpAddress,
        [int]$TimeoutSeconds,
        [string[]]$VmNames
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-Connection -ComputerName $IpAddress -Count 1 -Quiet) {
            Write-Host "      [+] VM $IpAddress is online!" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Fail-LmnBatch -Message "VM $IpAddress did not become reachable within $TimeoutSeconds seconds" -VmNames $VmNames
}

$ProjectRoot = Split-Path $PSScriptRoot -Parent
$HarvesterFeedsSource = Join-Path $ProjectRoot "Backend-Harvester\feeds.json"
$HarvesterCodeSource = Join-Path $ProjectRoot "Backend-Harvester\main.py"
$PublisherCodeSource = Join-Path $ProjectRoot "Backend-Publisher\main.py"
$HostTemp = Join-Path $ProjectRoot "news_to_publish_temp.json"

$RequiredLocalSources = @(
    $HarvesterFeedsSource,
    $HarvesterCodeSource,
    $PublisherCodeSource
)
foreach ($sourcePath in $RequiredLocalSources) {
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        Write-Host "[ERROR] Required repository source file was not found: $sourcePath" -ForegroundColor Red
        Write-Host "Run the batch from a complete Little Mere News checkout; no VMs were started." -ForegroundColor Yellow
        exit 1
    }
}

$lockPath = Join-Path $ProjectRoot "lmn-batch.lock"
try {
    $batchLock = [System.IO.File]::Open(
        $lockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
} catch {
    Write-Host "[ERROR] Another Little Mere News batch execution already owns the orchestration lock." -ForegroundColor Red
    exit 1
}

try {
    $KnownHostsFile = if ($env:LMN_KNOWN_HOSTS_FILE) {
        $env:LMN_KNOWN_HOSTS_FILE
    } else {
        Join-Path (Join-Path $HOME ".ssh") "known_hosts"
    }

    if (-not (Test-Path -LiteralPath $KnownHostsFile -PathType Leaf)) {
        Write-Host "[ERROR] Trusted SSH known_hosts file was not found: $KnownHostsFile" -ForegroundColor Red
        Write-Host "Verify each VM host-key fingerprint through a trusted channel and enroll it before running the batch." -ForegroundColor Yellow
        exit 1
    }

    $VmReadyTimeoutSeconds = 120
    if ($env:LMN_VM_READY_TIMEOUT_SECONDS) {
        $parsedVmReadyTimeout = 0
        if (-not [int]::TryParse($env:LMN_VM_READY_TIMEOUT_SECONDS, [ref]$parsedVmReadyTimeout) -or $parsedVmReadyTimeout -lt 5 -or $parsedVmReadyTimeout -gt 600) {
            Write-Host "[ERROR] LMN_VM_READY_TIMEOUT_SECONDS must be an integer from 5 to 600." -ForegroundColor Red
            exit 1
        }
        $VmReadyTimeoutSeconds = $parsedVmReadyTimeout
    }

    $SshOptions = @(
        "-o", "StrictHostKeyChecking=yes",
        "-o", "UserKnownHostsFile=$KnownHostsFile",
        "-o", "BatchMode=yes"
    )

    $VMs = "LMN-Harvester", "LMN-Brain", "LMN-Publisher"
    $HarvesterHost = "lmnadmin@10.0.100.10"
    $PublisherHost = "lmnadmin@10.0.100.30"
    $HarvesterQueue = "/home/lmnadmin/news_to_publish.json"
    $PublisherInbound = "/home/lmnadmin/news_to_publish.inbound.json"
    $PublisherRetry = "/home/lmnadmin/news_to_publish.retry.json"
    $PublisherRejected = "/home/lmnadmin/news_to_publish.rejected.json"
    $PublisherEnvFile = "/home/lmnadmin/.config/lmn/publisher.env"

    # The remote environment file is provisioned manually on the trusted Publisher VM.
    # Secret values are expanded only by the remote shell and are never interpolated
    # into this local SSH command string.
    $PublisherEnvCheck = "test -r '$PublisherEnvFile' && set -a && . '$PublisherEnvFile' && set +a && test -n `"`$SUPABASE_URL`" && test -n `"`$SUPABASE_KEY`""
    $PublisherCommand = "$PublisherEnvCheck && export LMN_INPUT_FILE='$PublisherInbound' && export LMN_RETRY_FILE='$PublisherRetry' && export LMN_REJECTED_FILE='$PublisherRejected' && /home/lmnadmin/publisher-env/bin/python /home/lmnadmin/main.py"

    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host " LMN BATCH PROCESSOR - INITIALIZING      " -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan

    Write-Host "[1/6] Starting Virtual Machines ($VMs)..." -ForegroundColor Yellow
    Start-VM -Name $VMs -ErrorAction SilentlyContinue

    Write-Host "      Waiting for boot and network connection (timeout ${VmReadyTimeoutSeconds}s per VM)..." -ForegroundColor DarkGray
    $IPs = "10.0.100.10", "10.0.100.20", "10.0.100.30"
    foreach ($ip in $IPs) {
        Wait-LmnVmNetwork -IpAddress $ip -TimeoutSeconds $VmReadyTimeoutSeconds -VmNames $VMs
    }
    Write-Host "      Waiting for services (SSH, Ollama) to initialize (15s)..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 15

    Write-Host "[2/6] Verifying trusted SSH endpoints and transferring Python logic..." -ForegroundColor Yellow
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Publisher server-side environment is missing or incomplete" -Command {
        ssh @SshOptions $PublisherHost $PublisherEnvCheck
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer feeds.json to Harvester" -Command {
        scp @SshOptions $HarvesterFeedsSource "${HarvesterHost}:/home/lmnadmin/feeds.json" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Harvester code" -Command {
        scp @SshOptions $HarvesterCodeSource "${HarvesterHost}:/home/lmnadmin/main.py" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Publisher code" -Command {
        scp @SshOptions $PublisherCodeSource "${PublisherHost}:/home/lmnadmin/main.py" | Out-Null
    }

    Write-Host "[3/6] Draining retained Publisher inbound/retry state before harvesting new work..." -ForegroundColor Yellow
    & ssh @SshOptions $PublisherHost $PublisherCommand
    $preflightExit = $LASTEXITCODE
    if ($preflightExit -ne 0) {
        Write-Host "      [WARN] Publisher reported retained/rejected work or an unsafe queue result (exit $preflightExit)." -ForegroundColor Yellow
        Write-Host "      No new Harvester batch will be created or transferred this run; inspect Publisher retry/quarantine state." -ForegroundColor Yellow
        Stop-LmnCluster -Names $VMs
        exit $preflightExit
    }

    Write-Host "[4/6] Triggering LMN-Harvester (Data Collection & AI Processing)..." -ForegroundColor Yellow
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Harvester failed; existing handoff remains recoverable" -Command {
        ssh @SshOptions $HarvesterHost "/home/lmnadmin/harvester-env/bin/python /home/lmnadmin/main.py"
    }
    Write-Host "      Harvester completed and durable handoff state is ready." -ForegroundColor Green

    Write-Host "[5/6] Transferring new inbound batch and triggering LMN-Publisher..." -ForegroundColor Yellow
    Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue

    & scp @SshOptions "${HarvesterHost}:$HarvesterQueue" $HostTemp 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail-LmnBatch -Message "Could not pull Harvester handoff; remote batch retained" -VmNames $VMs
    }

    & scp @SshOptions $HostTemp "${PublisherHost}:$PublisherInbound" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail-LmnBatch -Message "Could not push Publisher inbound batch; Harvester source retained" -VmNames $VMs
    }

    Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue

    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Publisher inbound exists but Harvester source could not be cleared; replay remains deduplicatable" -Command {
        ssh @SshOptions $HarvesterHost "rm -f '$HarvesterQueue'"
    }

    & ssh @SshOptions $PublisherHost $PublisherCommand
    $publisherExit = $LASTEXITCODE
    if ($publisherExit -ne 0) {
        Write-Host "      [WARN] Publisher reported retryable/rejected work or an unsafe queue result (exit $publisherExit)." -ForegroundColor Yellow
        Write-Host "      Durable retry/quarantine state has been preserved; inspect it before treating the batch as successful." -ForegroundColor Yellow
        Stop-LmnCluster -Names $VMs
        exit $publisherExit
    }
    Write-Host "      Publisher drained the current inbound/retry workload successfully." -ForegroundColor Green

    Write-Host "[6/6] Shutting down VM cluster to conserve resources..." -ForegroundColor Yellow
    Stop-LmnCluster -Names $VMs

    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host " BATCH COMPLETED! The web portal has been updated." -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Cyan
    exit 0
} finally {
    if ($null -ne $batchLock) {
        $batchLock.Dispose()
    }
}
