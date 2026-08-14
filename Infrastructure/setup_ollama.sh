#!/bin/bash
set -euo pipefail

# Reviewed optional-runtime boundary. Update these values together after reviewing a
# newer official Ollama release/model identity; do not replace them with `latest`.
OLLAMA_VERSION="0.32.5"
OLLAMA_INSTALL_SCRIPT_SHA256="25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f"
OLLAMA_INSTALL_SCRIPT_URL="https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/install.sh"
OLLAMA_MODEL="llama3:8b"
# Ollama's official model library displays this content identifier for llama3:8b.
# The API returns the full digest; matching this reviewed 12-hex prefix prevents a
# silently moved tag from being accepted without a repository review/update.
OLLAMA_MODEL_DIGEST_PREFIX="365c0bd3c000"

if [[ ! "$OLLAMA_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "[ERROR] Invalid reviewed Ollama version." >&2
  exit 2
fi
if [[ ! "$OLLAMA_INSTALL_SCRIPT_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "[ERROR] Invalid reviewed Ollama installer SHA-256." >&2
  exit 2
fi
if [[ ! "$OLLAMA_MODEL_DIGEST_PREFIX" =~ ^[0-9a-f]{12}$ ]]; then
  echo "[ERROR] Invalid reviewed Ollama model digest prefix." >&2
  exit 2
fi

echo "[1/5] Installing bootstrap prerequisites..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl python3

INSTALLER="$(mktemp)"
cleanup() {
  rm -f "$INSTALLER"
}
trap cleanup EXIT

echo "[2/5] Downloading reviewed Ollama ${OLLAMA_VERSION} installer asset..."
curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 \
  "$OLLAMA_INSTALL_SCRIPT_URL" -o "$INSTALLER"
printf '%s  %s\n' "$OLLAMA_INSTALL_SCRIPT_SHA256" "$INSTALLER" | sha256sum --check --strict -

# The downloaded script is a versioned GitHub release asset whose exact bytes were
# verified above. OLLAMA_VERSION additionally pins the package version it requests.
echo "[3/5] Executing checksum-verified Ollama installer..."
OLLAMA_VERSION="$OLLAMA_VERSION" sh "$INSTALLER"

echo "[4/5] Configuring Ollama internal-network listener..."
mkdir -p /etc/systemd/system/ollama.service.d
cat <<'EOF' > /etc/systemd/system/ollama.service.d/environment.conf
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
systemctl daemon-reload
systemctl restart ollama

for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:11434/api/tags >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:11434/api/tags >/dev/null

echo "[5/5] Pulling and verifying reviewed model identity ${OLLAMA_MODEL}..."
ollama pull "$OLLAMA_MODEL"
ACTUAL_DIGEST="$(
  curl --fail --silent http://127.0.0.1:11434/api/tags |
    python3 -c 'import json, sys
payload = json.load(sys.stdin)
target = sys.argv[1]
for model in payload.get("models", []):
    if model.get("name") == target or model.get("model") == target:
        digest = model.get("digest")
        if isinstance(digest, str):
            print(digest)
            raise SystemExit(0)
raise SystemExit(3)' "$OLLAMA_MODEL"
)"

case "$ACTUAL_DIGEST" in
  "${OLLAMA_MODEL_DIGEST_PREFIX}"*) ;;
  *)
    echo "[ERROR] Ollama model digest does not match the repository-reviewed identity." >&2
    echo "Expected prefix: ${OLLAMA_MODEL_DIGEST_PREFIX}" >&2
    echo "Actual digest:   ${ACTUAL_DIGEST:-<missing>}" >&2
    echo "Review the upstream model before changing the pinned identifier." >&2
    exit 1
    ;;
esac

ollama --version
echo "Verified model ${OLLAMA_MODEL} digest ${ACTUAL_DIGEST}."
echo "Ollama provisioning completed with reviewed version and model boundaries."
