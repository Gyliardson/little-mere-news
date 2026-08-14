<#
.SYNOPSIS
Master orchestration script for the Little Mere News batch processing architecture.

.DESCRIPTION
Starts the required Hyper-V Virtual Machines, acquires a host-global lock keyed to
those shared VM resources, recovers/drains Publisher-owned spool work, atomically
claims one Harvester pending batch, and transfers it by immutable batch identity.
No launcher unlinks the mutable Harvester pending pathname and no producer replaces
a Publisher file that a consumer may already own. Worker/SSH/SCP failures propagate
non-zero while recoverable claim/spool state remains durable.
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
    Write-Host "      Recoverable queue/claim files were not intentionally deleted." -ForegroundColor Yellow
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

function Invoke-PublisherDrain {
    param(
        [string[]]$SshOptions,
        [string]$PublisherHost,
        [string]$PublisherSpool,
        [string]$PublisherRetry,
        [string]$PublisherRejected,
        [string]$PublisherEnvCheck
    )

    # Bounded loop prevents a malformed/external producer from causing an infinite
    # launcher session while still draining all repository-owned queued batches.
    for ($iteration = 0; $iteration -lt 512; $iteration++) {
        $claimOutput = & ssh @SshOptions $PublisherHost "/home/lmnadmin/publisher-env/bin/python /home/lmnadmin/spool.py claim-next --spool '$PublisherSpool'"
        $claimExit = $LASTEXITCODE
        if ($claimExit -ne 0) {
            Write-Host "      [ERROR] Publisher spool claim failed (exit $claimExit)." -ForegroundColor Red
            return $claimExit
        }

        $publisherInput = ([string]$claimOutput).Trim()
        $hasClaim = -not [string]::IsNullOrWhiteSpace($publisherInput)
        if (-not $hasClaim) {
            # A deliberately absent input pathname allows main.py to drain retry state
            # without giving it ownership of an inbox pathname it never claimed.
            $publisherInput = "$PublisherSpool/processing/__no_inbound__.json"
        }

        $publisherCommand = "$PublisherEnvCheck && export LMN_INPUT_FILE='$publisherInput' && export LMN_RETRY_FILE='$PublisherRetry' && export LMN_REJECTED_FILE='$PublisherRejected' && /home/lmnadmin/publisher-env/bin/python /home/lmnadmin/main.py"
        & ssh @SshOptions $PublisherHost $publisherCommand
        $publisherExit = $LASTEXITCODE
        if ($publisherExit -ne 0) {
            return $publisherExit
        }

        if (-not $hasClaim) {
            return 0
        }
    }

    Write-Host "      [ERROR] Publisher spool exceeded the bounded 512-batch drain budget." -ForegroundColor Red
    return 1
}

$ProjectRoot = Split-Path $PSScriptRoot -Parent
$HarvesterFeedsSource = Join-Path $ProjectRoot "Backend-Harvester\feeds.json"
$HarvesterCodeSource = Join-Path $ProjectRoot "Backend-Harvester\main.py"
$HarvesterClaimSource = Join-Path $ProjectRoot "Backend-Harvester\queue_claim.py"
$PublisherCodeSource = Join-Path $ProjectRoot "Backend-Publisher\main.py"
$PublisherSpoolSource = Join-Path $ProjectRoot "Backend-Publisher\spool.py"
$HostLockHelperSource = Join-Path $PSScriptRoot "Lmn-HostLock.ps1"
$HostTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("lmn-handoff-{0}.json" -f [guid]::NewGuid().ToString("N"))

$RequiredLocalSources = @(
    $HarvesterFeedsSource,
    $HarvesterCodeSource,
    $HarvesterClaimSource,
    $PublisherCodeSource,
    $PublisherSpoolSource,
    $HostLockHelperSource
)
foreach ($sourcePath in $RequiredLocalSources) {
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        Write-Host "[ERROR] Required repository source file was not found: $sourcePath" -ForegroundColor Red
        Write-Host "Run the batch from a complete Little Mere News checkout; no VMs were started." -ForegroundColor Yellow
        exit 1
    }
}

. $HostLockHelperSource

$VMs = "LMN-Harvester", "LMN-Brain", "LMN-Publisher"
$SharedResourceIds = @(
    "hyperv:LMN-Harvester",
    "hyperv:LMN-Brain",
    "hyperv:LMN-Publisher",
    "ssh:10.0.100.10",
    "ssh:10.0.100.20",
    "ssh:10.0.100.30"
)
$batchLock = $null
try {
    # The lock lives under host-global CommonApplicationData and is keyed only by the
    # shared VM/resource identity. Two clones/worktrees on this Windows host therefore
    # contend for exactly the same lock instead of each owning a repository-local file.
    $batchLock = Enter-LmnHostLock -ResourceIds $SharedResourceIds
} catch {
    Write-Host "[ERROR] Could not acquire the Little Mere News shared-resource lock: $($_.Exception.Message)" -ForegroundColor Red
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

    $HarvesterHost = "lmnadmin@10.0.100.10"
    $PublisherHost = "lmnadmin@10.0.100.30"
    $HarvesterPending = "/home/lmnadmin/news_to_publish.json"
    $PublisherSpool = "/home/lmnadmin/.local/state/lmn/publisher-spool"
    $PublisherStageDir = "/home/lmnadmin/.local/state/lmn/publisher-staging"
    $PublisherRetry = "/home/lmnadmin/news_to_publish.retry.json"
    $PublisherRejected = "/home/lmnadmin/news_to_publish.rejected.json"
    $PublisherEnvFile = "/home/lmnadmin/.config/lmn/publisher.env"

    # The remote environment file is provisioned manually on the trusted Publisher VM.
    # Secret values are expanded only by the remote shell and are never interpolated
    # into this local SSH command string.
    $PublisherEnvCheck = "test -r '$PublisherEnvFile' && set -a && . '$PublisherEnvFile' && set +a && test -n `"`$SUPABASE_URL`" && test -n `"`$SUPABASE_KEY`""

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

    Write-Host "[2/6] Verifying trusted SSH endpoints and transferring worker/ownership logic..." -ForegroundColor Yellow
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Publisher server-side environment is missing or incomplete" -Command {
        ssh @SshOptions $PublisherHost $PublisherEnvCheck
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer feeds.json to Harvester" -Command {
        scp @SshOptions $HarvesterFeedsSource "${HarvesterHost}:/home/lmnadmin/feeds.json" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Harvester code" -Command {
        scp @SshOptions $HarvesterCodeSource "${HarvesterHost}:/home/lmnadmin/main.py" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Harvester claim helper" -Command {
        scp @SshOptions $HarvesterClaimSource "${HarvesterHost}:/home/lmnadmin/queue_claim.py" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Publisher code" -Command {
        scp @SshOptions $PublisherCodeSource "${PublisherHost}:/home/lmnadmin/main.py" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not transfer Publisher spool helper" -Command {
        scp @SshOptions $PublisherSpoolSource "${PublisherHost}:/home/lmnadmin/spool.py" | Out-Null
    }
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Could not initialize Publisher spool directories" -Command {
        ssh @SshOptions $PublisherHost "mkdir -p '$PublisherSpool/inbox' '$PublisherSpool/processing' '$PublisherStageDir'"
    }

    Write-Host "[3/6] Recovering/draining retained Publisher processing, inbox and retry state..." -ForegroundColor Yellow
    $preflightExit = Invoke-PublisherDrain -SshOptions $SshOptions -PublisherHost $PublisherHost -PublisherSpool $PublisherSpool -PublisherRetry $PublisherRetry -PublisherRejected $PublisherRejected -PublisherEnvCheck $PublisherEnvCheck
    if ($preflightExit -ne 0) {
        Write-Host "      [WARN] Publisher reported retained/rejected work or an unsafe queue result (exit $preflightExit)." -ForegroundColor Yellow
        Write-Host "      No new Harvester batch will be created this run; claimed/spooled work remains recoverable." -ForegroundColor Yellow
        Stop-LmnCluster -Names $VMs
        exit $preflightExit
    }

    Write-Host "[4/6] Triggering LMN-Harvester (Data Collection & AI Processing)..." -ForegroundColor Yellow
    Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Harvester failed; existing ownership state remains recoverable" -Command {
        ssh @SshOptions $HarvesterHost "/home/lmnadmin/harvester-env/bin/python /home/lmnadmin/main.py"
    }
    Write-Host "      Harvester completed and pending state is durable." -ForegroundColor Green

    Write-Host "[5/6] Claiming one Harvester batch and enqueuing immutable Publisher work..." -ForegroundColor Yellow
    Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue

    $claimOutput = & ssh @SshOptions $HarvesterHost "/home/lmnadmin/harvester-env/bin/python /home/lmnadmin/queue_claim.py claim --pending '$HarvesterPending'"
    $claimExit = $LASTEXITCODE
    if ($claimExit -ne 0) {
        Fail-LmnBatch -Message "Could not claim Harvester pending state" -VmNames $VMs
    }
    $HarvesterClaim = ([string]$claimOutput).Trim()

    if (-not [string]::IsNullOrWhiteSpace($HarvesterClaim)) {
        $BatchId = [System.IO.Path]::GetFileNameWithoutExtension($HarvesterClaim)
        if ($BatchId -notmatch '^batch-[0-9a-f]{32}$') {
            Fail-LmnBatch -Message "Harvester returned an invalid batch identity" -VmNames $VMs
        }

        & scp @SshOptions "${HarvesterHost}:$HarvesterClaim" $HostTemp 2>$null
        if ($LASTEXITCODE -ne 0) {
            Fail-LmnBatch -Message "Could not pull claimed Harvester batch; exact remote claim retained" -VmNames $VMs
        }

        $PublisherStaging = "$PublisherStageDir/$BatchId-$([guid]::NewGuid().ToString('N')).json"
        & scp @SshOptions $HostTemp "${PublisherHost}:$PublisherStaging" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Fail-LmnBatch -Message "Could not stage Publisher batch; Harvester claim retained" -VmNames $VMs
        }

        & ssh @SshOptions $PublisherHost "/home/lmnadmin/publisher-env/bin/python /home/lmnadmin/spool.py enqueue --staging '$PublisherStaging' --spool '$PublisherSpool' --batch-id '$BatchId'"
        if ($LASTEXITCODE -ne 0) {
            Fail-LmnBatch -Message "Could not publish staged batch into immutable Publisher inbox; Harvester claim retained" -VmNames $VMs
        }

        # Acknowledge only the exact claim after Publisher spool ownership is durable.
        # A newer Harvester pending file, if any, has a different pathname and survives.
        Invoke-CheckedExternal -VmNames $VMs -FailureMessage "Publisher owns batch but exact Harvester claim could not be acknowledged; replay is idempotent" -Command {
            ssh @SshOptions $HarvesterHost "/home/lmnadmin/harvester-env/bin/python /home/lmnadmin/queue_claim.py complete --pending '$HarvesterPending' --batch-id '$BatchId'"
        }
        Write-Host "      Batch $BatchId transferred into immutable Publisher spool ownership." -ForegroundColor Green
    } else {
        Write-Host "      No Harvester pending batch required transfer." -ForegroundColor DarkGray
    }

    Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue

    $publisherExit = Invoke-PublisherDrain -SshOptions $SshOptions -PublisherHost $PublisherHost -PublisherSpool $PublisherSpool -PublisherRetry $PublisherRetry -PublisherRejected $PublisherRejected -PublisherEnvCheck $PublisherEnvCheck
    if ($publisherExit -ne 0) {
        Write-Host "      [WARN] Publisher reported retryable/rejected work or an unsafe queue result (exit $publisherExit)." -ForegroundColor Yellow
        Write-Host "      Processing/inbox/retry/quarantine ownership remains durable for inspection/recovery." -ForegroundColor Yellow
        Stop-LmnCluster -Names $VMs
        exit $publisherExit
    }
    Write-Host "      Publisher drained all currently claimed/inbox/retry workload successfully." -ForegroundColor Green

    Write-Host "[6/6] Shutting down VM cluster to conserve resources..." -ForegroundColor Yellow
    Stop-LmnCluster -Names $VMs

    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host " BATCH COMPLETED! The web portal has been updated." -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Cyan
    exit 0
} finally {
    Remove-Item $HostTemp -Force -ErrorAction SilentlyContinue
    if ($null -ne $batchLock) {
        $batchLock.Dispose()
    }
}
