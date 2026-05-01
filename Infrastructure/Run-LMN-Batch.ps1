<#
.SYNOPSIS
Master orchestration script for the Little Mere News batch processing architecture.

.DESCRIPTION
Starts the required Hyper-V Virtual Machines, waits for the network to initialize,
triggers the backend processing scripts via SSH, and gracefully shuts down the VMs upon completion.
Designed to be executed on-demand or scheduled via Windows Task Scheduler.
#>

# ============================================================================
# CLOUD CREDENTIALS (Automatic Loading)
# The script automatically reads the hidden ".env" file in the project root.
# ============================================================================
$envFilePath = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFilePath) {
    Get-Content $envFilePath | Where-Object { $_ -match '=' -and $_ -notmatch '^#' } | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        Set-Item -Path "env:\$name" -Value $value.Trim()
    }
} else {
    Write-Host "[ERROR] .env file not found in the project root!" -ForegroundColor Red
    Write-Host "Please, copy .env.example to .env and insert your keys." -ForegroundColor Yellow
    Pause
    exit
}

$SUPABASE_URL = $env:SUPABASE_URL
$SUPABASE_KEY = $env:SUPABASE_KEY
# ============================================================================

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " LMN BATCH PROCESSOR - INITIALIZING      " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Start Virtual Machines
$VMs = "LMN-Harvester", "LMN-Brain", "LMN-Publisher"
Write-Host "[1/5] Starting Virtual Machines ($VMs)..." -ForegroundColor Yellow
Start-VM -Name $VMs -ErrorAction SilentlyContinue

# Wait for network connectivity (Ping)
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

# 2. Transfer Python Scripts
Write-Host "[2/5] Transferring Python logic to VMs..." -ForegroundColor Yellow
scp -o StrictHostKeyChecking=no ".\Backend-Harvester\feeds.json" lmnadmin@10.0.100.10:/home/lmnadmin/ | Out-Null
scp -o StrictHostKeyChecking=no ".\Backend-Harvester\main.py" lmnadmin@10.0.100.10:/home/lmnadmin/ | Out-Null
scp -o StrictHostKeyChecking=no ".\Backend-Publisher\main.py" lmnadmin@10.0.100.30:/home/lmnadmin/ | Out-Null

# 3. Execute Data Collection and AI Processing
Write-Host "[3/5] Triggering LMN-Harvester (Data Collection & AI Processing)..." -ForegroundColor Yellow
Write-Host "      This might take several minutes depending on the AI workload." -ForegroundColor DarkGray
ssh -o StrictHostKeyChecking=no lmnadmin@10.0.100.10 "/home/lmnadmin/harvester-env/bin/python /home/lmnadmin/main.py"
Write-Host "      Collection and translation completed successfully!" -ForegroundColor Green

# 4. Bridge Transfer & Cloud Upload
Write-Host "[4/5] Bridging data and triggering LMN-Publisher (Supabase Upload)..." -ForegroundColor Yellow
# Pull from Harvester to Host (Temporary)
scp -o StrictHostKeyChecking=no lmnadmin@10.0.100.10:/home/lmnadmin/news_to_publish.json ".\news_to_publish_temp.json" 2>$null
# Push from Host to Publisher if file exists
if (Test-Path ".\news_to_publish_temp.json") {
    scp -o StrictHostKeyChecking=no ".\news_to_publish_temp.json" lmnadmin@10.0.100.30:/home/lmnadmin/news_to_publish.json 2>$null
    Remove-Item ".\news_to_publish_temp.json" -Force
} else {
    Write-Host "      [INFO] No new articles collected today." -ForegroundColor DarkGray
}

# Execute Publisher injecting Supabase Credentials securely via environment variables
ssh -o StrictHostKeyChecking=no lmnadmin@10.0.100.30 "export SUPABASE_URL='$SUPABASE_URL' && export SUPABASE_KEY='$SUPABASE_KEY' && /home/lmnadmin/publisher-env/bin/python /home/lmnadmin/main.py"
Write-Host "      News articles uploaded to the cloud database!" -ForegroundColor Green

# 5. Graceful Shutdown
Write-Host "[5/5] Shutting down VM cluster to conserve resources..." -ForegroundColor Yellow
Stop-VM -Name $VMs -Force -ErrorAction SilentlyContinue

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " BATCH COMPLETED! The web portal has been updated." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Pause
