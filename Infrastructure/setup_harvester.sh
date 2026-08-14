#!/bin/bash
set -euo pipefail

REQUIREMENTS_FILE="${1:-}"
if [[ -z "$REQUIREMENTS_FILE" || ! -f "$REQUIREMENTS_FILE" ]]; then
  echo "[ERROR] Expected repository-reviewed Harvester requirements file as argument 1." >&2
  exit 2
fi

if grep -Ev '^(#|[[:space:]]*$|[A-Za-z0-9_.-]+==[^[:space:]]+)$' "$REQUIREMENTS_FILE" | grep -q .; then
  echo "[ERROR] Harvester requirements must contain only blank/comment lines or exact == pins." >&2
  exit 2
fi

echo "[1/3] Updating packages and installing Python..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-pip python3-venv

echo "[2/3] Creating Virtual Environment (harvester-env)..."
rm -rf /home/lmnadmin/harvester-env
sudo -u lmnadmin python3 -m venv /home/lmnadmin/harvester-env

echo "[3/3] Installing repository-reviewed dependencies..."
sudo -u lmnadmin /home/lmnadmin/harvester-env/bin/python -m pip install --requirement "$REQUIREMENTS_FILE"
sudo -u lmnadmin /home/lmnadmin/harvester-env/bin/python -m pip check

echo "Harvester provisioning completed from pinned requirements."
