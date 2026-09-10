#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/botify-demo}"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1
if [[ "${EUID}" -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi

configure_file() {
  local target="$1" template="$2"
  if [[ -e "${target}" && "${FORCE}" -ne 1 ]]; then
    echo "Keeping ${target}; use --force only after reviewing a backup requirement."
    return
  fi
  if [[ -e "${target}" ]]; then
    cp -a "${target}" "${target}.bak.$(date +%Y%m%d%H%M%S)"
  fi
  install -o botify -g botify -m 0600 "${template}" "${target}"
}

configure_file "${APP_DIR}/.env" "${APP_DIR}/deploy/ec2/.env.example"
configure_file "${APP_DIR}/ec2-agent/.env" "${APP_DIR}/ec2-agent/.env.example"
echo "Configuration files are in place. Edit them before starting services."

