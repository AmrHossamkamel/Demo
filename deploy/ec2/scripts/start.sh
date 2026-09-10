#!/usr/bin/env bash
set -euo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi
systemctl enable --now botify-demo-agent.service botify-demo-app.service
systemctl --no-pager --full status botify-demo-agent.service botify-demo-app.service

