#!/bin/bash
# ==============================================================================
# Botify Observability Demo Testing Platform - EC2 Deployment Script
# ==============================================================================

echo "================================================================"
echo "  Deploying Botify Demo Platform on EC2 Server (Port 9000)"
echo "================================================================"

# 1. Ensure Python3 and pip are installed
if ! command -v python3 &> /dev/null; then
    echo "[!] Python3 not found. Installing python3 and python3-pip..."
    sudo yum install -y python3 python3-pip || sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi

# 2. Create required log directories with full read/write permissions
echo "[+] Creating log directories..."
mkdir -p ./data/logs
sudo mkdir -p /var/log/botify_demo
sudo chmod -R 777 /var/log/botify_demo 2>/dev/null || true

# 3. Install dependencies
echo "[+] Installing Python package dependencies..."
python3 -m pip install -r requirements.txt --quiet

# 4. Copy default environment variables if .env doesn't exist
if [ ! -f .env ]; then
    echo "[+] Creating .env file from template..."
    cp .env.example .env
fi

# 5. Automatically configure Splunk file monitoring if Splunk CLI is present
if command -v /opt/splunk/bin/splunk &> /dev/null; then
    echo "[+] Configuring Splunk to monitor /var/log/botify_demo/app.log into index main..."
    sudo /opt/splunk/bin/splunk add monitor /var/log/botify_demo/app.log -index main -sourcetype _json -auth admin:changeme 2>/dev/null || true
fi

# 6. Launch Backend Engine
echo "================================================================"
echo "  [SUCCESS] Botify Demo Platform is ready on EC2!"
echo "  Access Web UI at: http://$(curl -s http://checkip.amazonaws.com 2>/dev/null || echo 'YOUR_EC2_IP'):9000"
echo "================================================================"

python3 run.py
