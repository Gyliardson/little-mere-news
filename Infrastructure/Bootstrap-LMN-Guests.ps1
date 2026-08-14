<#
.SYNOPSIS
Transfers the repository-reviewed guest bootstrap inputs and executes them on LMN VMs.

.DESCRIPTION
This is the supported post-Ubuntu guest bootstrap path. Python workers receive the
exact requirements.txt files from the current repository checkout; guest setup scripts
install only from those transferred manifests. SSH host identity is verified against a
pre-enrolled known_hosts file. Ollama remains optional and uses its separately bounded
setup script.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

$KnownHostsFile = if ($env:LMN_KNOWN_HOSTS_FILE) {
    $env:LMN_KNOWN_HOSTS_FILE
} else {
    Join-Path (Join-Path $HOME ".ssh") "known_hosts"
}

if (-not (Test-Path -LiteralPath $KnownHostsFile -PathType Leaf)) {
    throw "Trusted SSH known_hosts file was not found: $KnownHostsFile"
}

$SshOptions = @(
    "-o", "StrictHostKeyChecking=yes",
    "-o", "UserKnownHostsFile=$KnownHostsFile",
    "-o", "BatchMode=yes"
)

$HarvesterHost = "lmnadmin@10.0.100.10"
$BrainHost = "lmnadmin@10.0.100.20"
$PublisherHost = "lmnadmin@10.0.100.30"
$RemoteBootstrapDir = "/home/lmnadmin/lmn-bootstrap"

$HarvesterRequirements = Join-Path $ProjectRoot "Backend-Harvester\requirements.txt"
$PublisherRequirements = Join-Path $ProjectRoot "Backend-Publisher\requirements.txt"
$HarvesterSetup = Join-Path $PSScriptRoot "setup_harvester.sh"
$PublisherSetup = Join-Path $PSScriptRoot "setup_publisher.sh"
$OllamaSetup = Join-Path $PSScriptRoot "setup_ollama.sh"

$RequiredSources = @(
    $HarvesterRequirements,
    $PublisherRequirements,
    $HarvesterSetup,
    $PublisherSetup,
    $OllamaSetup
)
foreach ($source in $RequiredSources) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required reviewed bootstrap source is missing: $source"
    }
}

function Invoke-CheckedExternal {
    param(
        [scriptblock]$Command,
        [string]$FailureMessage
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit $LASTEXITCODE)"
    }
}

function Initialize-RemoteBootstrapDir {
    param([string]$HostName)
    Invoke-CheckedExternal -FailureMessage "Could not initialize bootstrap directory on $HostName" -Command {
        ssh @SshOptions $HostName "mkdir -p '$RemoteBootstrapDir' && chmod 700 '$RemoteBootstrapDir'"
    }
}

Write-Host "[1/3] Bootstrapping Harvester from repository requirements..." -ForegroundColor Yellow
Initialize-RemoteBootstrapDir -HostName $HarvesterHost
Invoke-CheckedExternal -FailureMessage "Could not transfer Harvester requirements" -Command {
    scp @SshOptions $HarvesterRequirements "${HarvesterHost}:$RemoteBootstrapDir/harvester-requirements.txt" | Out-Null
}
Invoke-CheckedExternal -FailureMessage "Could not transfer Harvester setup" -Command {
    scp @SshOptions $HarvesterSetup "${HarvesterHost}:$RemoteBootstrapDir/setup_harvester.sh" | Out-Null
}
Invoke-CheckedExternal -FailureMessage "Harvester guest bootstrap failed" -Command {
    ssh @SshOptions $HarvesterHost "sudo bash '$RemoteBootstrapDir/setup_harvester.sh' '$RemoteBootstrapDir/harvester-requirements.txt'"
}

Write-Host "[2/3] Bootstrapping Publisher from repository requirements..." -ForegroundColor Yellow
Initialize-RemoteBootstrapDir -HostName $PublisherHost
Invoke-CheckedExternal -FailureMessage "Could not transfer Publisher requirements" -Command {
    scp @SshOptions $PublisherRequirements "${PublisherHost}:$RemoteBootstrapDir/publisher-requirements.txt" | Out-Null
}
Invoke-CheckedExternal -FailureMessage "Could not transfer Publisher setup" -Command {
    scp @SshOptions $PublisherSetup "${PublisherHost}:$RemoteBootstrapDir/setup_publisher.sh" | Out-Null
}
Invoke-CheckedExternal -FailureMessage "Publisher guest bootstrap failed" -Command {
    ssh @SshOptions $PublisherHost "sudo bash '$RemoteBootstrapDir/setup_publisher.sh' '$RemoteBootstrapDir/publisher-requirements.txt'"
}

if ($env:LMN_SKIP_OLLAMA_BOOTSTRAP -eq "1") {
    Write-Host "[3/3] Ollama bootstrap skipped by LMN_SKIP_OLLAMA_BOOTSTRAP=1." -ForegroundColor DarkGray
} else {
    Write-Host "[3/3] Bootstrapping reviewed Ollama runtime/model boundary..." -ForegroundColor Yellow
    Initialize-RemoteBootstrapDir -HostName $BrainHost
    Invoke-CheckedExternal -FailureMessage "Could not transfer Ollama setup" -Command {
        scp @SshOptions $OllamaSetup "${BrainHost}:$RemoteBootstrapDir/setup_ollama.sh" | Out-Null
    }
    Invoke-CheckedExternal -FailureMessage "Ollama guest bootstrap failed" -Command {
        ssh @SshOptions $BrainHost "sudo bash '$RemoteBootstrapDir/setup_ollama.sh'"
    }
}

Write-Host "Guest bootstrap completed from repository-reviewed inputs." -ForegroundColor Green
