#!/usr/bin/env bash
set -euo pipefail
curl --fail --silent --show-error http://127.0.0.1:4100/api/v1/health >/dev/null
curl --fail --silent --show-error http://127.0.0.1:4100/ >/dev/null
curl --fail --silent --show-error http://127.0.0.1:4200/health >/dev/null
echo "Botify app and agent health checks passed."
