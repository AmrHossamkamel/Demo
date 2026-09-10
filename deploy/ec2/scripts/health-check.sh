#!/usr/bin/env bash
set -euo pipefail

APP_PORT="${APP_PORT:-9000}"
AGENT_PORT="${AGENT_PORT:-4210}"

# Support both the newer /api/v1/health and the legacy /health on the same app port.
(
  curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/api/v1/health" >/dev/null
) || (
  curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/health" >/dev/null
)
curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/" >/dev/null

# Support agent port (try 4210 by default, fall back to legacy 4200)
(
  curl --fail --silent --show-error "http://127.0.0.1:${AGENT_PORT}/health" >/dev/null
) || (
  curl --fail --silent --show-error "http://127.0.0.1:4200/health" >/dev/null
)

echo "Botify app (:${APP_PORT}) and agent (:${AGENT_PORT}) health checks passed."
