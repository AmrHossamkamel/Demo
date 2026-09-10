#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/botify-demo}"
PURGE=0
YES=0
for arg in "$@"; do [[ "${arg}" == "--purge" ]] && PURGE=1; [[ "${arg}" == "--yes" ]] && YES=1; done
if [[ "${EUID}" -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi
if [[ "${PURGE}" -eq 1 && "${YES}" -ne 1 ]]; then echo "Refusing purge without --purge --yes." >&2; exit 1; fi
systemctl disable --now botify-demo-app.service botify-demo-agent.service 2>/dev/null || true
rm -f /etc/systemd/system/botify-demo-app.service /etc/systemd/system/botify-demo-agent.service
systemctl daemon-reload
rm -f /etc/nginx/sites-enabled/botify-agent.conf /etc/nginx/sites-available/botify-agent.conf
if command -v nginx >/dev/null 2>&1; then nginx -t && systemctl reload nginx || true; fi
if [[ "${PURGE}" -eq 1 ]]; then rm -rf -- "${APP_DIR}"; fi
echo "Services removed; application data was preserved unless --purge --yes was supplied."

