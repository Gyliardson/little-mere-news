#!/bin/bash
set -e

echo "[1/4] Starting Ollama installation..."
# The official Ollama script handles everything
curl -fsSL https://ollama.com/install.sh -o install.sh
sh install.sh

echo "[2/4] Configuring Ollama to listen on the internal network (0.0.0.0)..."
mkdir -p /etc/systemd/system/ollama.service.d
cat <<EOF > /etc/systemd/system/ollama.service.d/environment.conf
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

echo "[3/4] Applying systemd configurations..."
systemctl daemon-reload
systemctl restart ollama

# Give the service time to start
sleep 5

echo "[4/4] Downloading Llama 3 model..."
ollama pull llama3

echo "Successfully completed!"
