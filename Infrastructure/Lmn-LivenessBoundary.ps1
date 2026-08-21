Set-StrictMode -Version Latest

function Test-LmnPublisherPreflightAllowsHarvester {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$PublisherExit
    )

    # The launcher must continue only on the scheduler-facing success contract.
    # Retained transient work is represented by Publisher exit zero; all non-zero
    # results remain unsafe and continue to abort before new Harvester collection.
    return $PublisherExit -eq 0
}
