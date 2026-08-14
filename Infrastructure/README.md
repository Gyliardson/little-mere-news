# Optional Hyper-V infrastructure

The scripts in this directory preserve the original Windows/Hyper-V deployment topology for Little Mere News. They are an optional runtime path, not a requirement for development, CI, browser tests, PostgreSQL/RLS verification, or portable worker deployments.

## Clone-location portability

`Install-LMN.ps1` and `Setup-LMN-Infrastructure.ps1` derive repository paths from their own script locations. A clone does not need to live under the original author's filesystem path.

Run the installer from an elevated PowerShell session on Windows 11 Pro/Enterprise:

```powershell
.\Infrastructure\Install-LMN.ps1
```

## Ubuntu ISO source and integrity

The setup keeps an explicit reviewed Ubuntu 24.04 LTS server-image URL rather than discovering an implicit `latest` image. If Canonical advances the point release or an operator intentionally selects another compatible image, set `LMN_UBUNTU_ISO_URL` to the reviewed **absolute HTTPS** image URL.

For the exact selected image, obtain its SHA-256 digest from Ubuntu's official release manifest through a trusted administrative/browser channel and set both values together when overriding the default:

```powershell
$env:LMN_UBUNTU_ISO_URL = "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso"
$env:LMN_UBUNTU_ISO_SHA256 = "<64-character-sha256>"
```

The setup script refuses non-HTTPS source overrides and refuses to reuse or mount an ISO unless its SHA-256 matches the expected digest. Missing/malformed digest input or a digest mismatch terminates Stage 2 before network/VM provisioning uses the image.

A SHA-256 comparison is an integrity check for the downloaded bytes. It does **not** independently authenticate the Ubuntu release origin if both the image and digest source were compromised. Treat the official release origin/manifest and the channel used to verify it as an external trust boundary.

Do not commit a mutable or guessed digest merely to make setup pass. When the configured Ubuntu point release changes, review the ISO URL and trusted digest together.

## Other trust boundaries

The batch runtime separately requires strict SSH host-key verification and Publisher-side secret provisioning as described in [`../docs/deployment.md`](../docs/deployment.md). Do not weaken those controls to simplify local setup.
