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

## Reviewed guest bootstrap

After Ubuntu, static IPs, SSH host keys and passwordless administrative access are configured, use the repository-owned host bootstrap instead of manually retyping package names on each guest:

```powershell
.\Infrastructure\Bootstrap-LMN-Guests.ps1
```

The script:

1. loads the exact `Backend-Harvester/requirements.txt` and `Backend-Publisher/requirements.txt` from the current checkout;
2. transfers those manifests and the matching setup scripts to the corresponding VMs over strict known-host SSH;
3. runs each guest setup with the transferred manifest as an explicit argument;
4. fails non-zero if transfer, installation or `pip check` fails;
5. optionally bootstraps the Brain/Ollama VM unless `LMN_SKIP_OLLAMA_BOOTSTRAP=1` is set.

The Python guest scripts reject a missing manifest and reject non-comment dependency lines that are not exact `==` pins. They no longer contain an independent list such as `pip install feedparser ...` or `pip install supabase ...`. The repository requirements files are therefore the reviewed direct-dependency contract for both CI and the supported VM bootstrap.

This is not a fully hermetic Python lock: transitive resolution, the Python interpreter and Ubuntu apt repositories remain upstream inputs. The important guarantee is narrower and testable: guest provisioning consumes the same version-pinned direct dependency manifest reviewed in the repository rather than silently selecting different top-level versions.

## Ollama trust/version boundary

Ollama remains optional and outside critical CI. `setup_ollama.sh` deliberately avoids the mutable `https://ollama.com/install.sh` pipeline previously used by this project.

The repository currently reviews:

- Ollama release `0.32.5`;
- the versioned GitHub release `install.sh` asset;
- installer SHA-256 `25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f`;
- model reference `llama3:8b`;
- reviewed model content identifier prefix `365c0bd3c000`.

The guest script downloads only that versioned release installer asset, verifies its SHA-256 before execution, passes the explicit Ollama version to the installer, pulls `llama3:8b`, then queries the local Ollama API and refuses the model if its full digest no longer begins with the reviewed identifier.

The model-library identifier is intentionally recorded as the 12-hex content identifier displayed by the official Ollama library, not misrepresented as a repository-known full SHA-256. If the upstream tag moves, bootstrap fails and requires an explicit repository review/update rather than silently accepting new model behavior.

Residual trust remains: the verified Ollama installer itself downloads the selected Ollama package over HTTPS, and the model registry remains an external source. The checksum/version boundary prevents executing a newly changed installer unnoticed; it is not a claim that the entire external software/model supply chain is independently reproducibly built by this repository.

## Other trust boundaries

The batch runtime separately requires strict SSH host-key verification and Publisher-side secret provisioning as described in [`../docs/deployment.md`](../docs/deployment.md). Do not weaken those controls to simplify local setup.

`ssh-keyscan` is not sufficient to establish trust by itself. Verify VM host-key fingerprints through a separate trusted channel before enrolling them in the operational `known_hosts` file.
