#!/usr/bin/env bash
set -euo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi
systemctl stop botify-demo-app.service botify-demo-agent.service

