#!/bin/bash
set -e

echo "[1/3] Updating packages and installing Python..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-pip python3-venv

echo "[2/3] Creating Virtual Environment (harvester-env)..."
sudo -u lmnadmin python3 -m venv /home/lmnadmin/harvester-env

echo "[3/3] Installing dependencies..."
sudo -u lmnadmin /home/lmnadmin/harvester-env/bin/pip install feedparser requests beautifulsoup4

echo "Harvester Provisioning Completed!"
