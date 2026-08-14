# Optional Hyper-V infrastructure

The scripts in this directory preserve the original Windows/Hyper-V deployment topology for Little Mere News. They are an optional runtime path, not a requirement for development, CI, browser tests, PostgreSQL/RLS verification, or portable worker deployments.

## Clone-location portability

`Install-LMN.ps1` and `Setup-LMN-Infrastructure.ps1` derive repository paths from their own script locations. A clone does not need to live under the original author's filesystem path.

Run the installer from an elevated PowerShell session on Windows 11 Pro/Enterprise:

```powershell
.\Infrastructure\Install-LMN.ps1
```

## Ubuntu ISO integrity

Before a real Hyper-V provisioning run, obtain the SHA-256 digest for the **exact ISO configured in `Setup-LMN-Infrastructure.ps1`** from Ubuntu's official release manifest through a trusted administrative/browser channel. Then set:

```powershell
$env:LMN_UBUNTU_ISO_SHA256 = "<64-character-sha256>"
```

The setup script refuses to reuse or mount an ISO unless its SHA-256 matches that expected digest. Missing/malformed digest input or a digest mismatch terminates provisioning before VM creation uses the image.

A SHA-256 comparison is an integrity check for the downloaded bytes. It does **not** independently authenticate the Ubuntu release origin if both the image and digest source were compromised. Treat the official release origin/manifest and the channel used to verify it as an external trust boundary.

Do not commit a mutable or guessed digest merely to make setup pass. When the configured Ubuntu point release changes, review the ISO URL and trusted digest together.

## Other trust boundaries

The batch runtime separately requires strict SSH host-key verification and Publisher-side secret provisioning as described in [`../docs/deployment.md`](../docs/deployment.md). Do not weaken those controls to simplify local setup.
