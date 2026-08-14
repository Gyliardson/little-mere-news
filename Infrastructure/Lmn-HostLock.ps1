Set-StrictMode -Version Latest

function Get-LmnHostLockPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ResourceIds,
        [string]$LockRootOverride
    )

    if ($ResourceIds.Count -eq 0) {
        throw "At least one shared resource identity is required for the LMN host lock."
    }

    $normalizedResources = @(
        $ResourceIds |
            ForEach-Object { $_.Trim().ToLowerInvariant() } |
            Where-Object { $_ } |
            Sort-Object -Unique
    )
    if ($normalizedResources.Count -eq 0) {
        throw "At least one non-empty shared resource identity is required for the LMN host lock."
    }

    $lockRoot = if ($LockRootOverride) {
        [System.IO.Path]::GetFullPath($LockRootOverride)
    } else {
        $commonData = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
        if (-not $commonData) {
            throw "Could not resolve a host-global CommonApplicationData directory."
        }
        Join-Path $commonData "LittleMereNews\locks"
    }

    $identity = [string]::Join("|", $normalizedResources)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($identity)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash($bytes)
    } finally {
        $sha256.Dispose()
    }
    $hash = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })
    return Join-Path $lockRoot "batch-$hash.lock"
}

function Enter-LmnHostLock {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ResourceIds,
        [string]$LockRootOverride
    )

    $lockPath = Get-LmnHostLockPath -ResourceIds $ResourceIds -LockRootOverride $LockRootOverride
    $parent = Split-Path $lockPath -Parent
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null

    try {
        return [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch [System.IO.IOException] {
        throw [System.IO.IOException]::new(
            "Another Little Mere News launcher already owns shared resources '$([string]::Join(', ', $ResourceIds))'.",
            $_.Exception
        )
    }
}
