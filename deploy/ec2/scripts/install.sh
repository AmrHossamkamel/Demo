#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/botify-demo}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then echo "Run as root (sudo)." >&2; exit 1; fi
id botify >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/botify --shell /usr/sbin/nologin botify
install -d -o botify -g botify "${APP_DIR}" "${APP_DIR}/data" "${APP_DIR}/ec2-agent/tmp-workloads"
cp -a "${REPO_DIR}/backend" "${REPO_DIR}/frontend" "${REPO_DIR}/run.py" "${REPO_DIR}/requirements.txt" "${REPO_DIR}/ec2-agent" "${REPO_DIR}/deploy" "${APP_DIR}/"
chown -R botify:botify "${APP_DIR}"

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --requirement "${APP_DIR}/requirements.txt"
(
  cd "${APP_DIR}/ec2-agent"
  npm ci
  npm run build
)

if [[ ! -e "${APP_DIR}/.env" ]]; then
  install -o botify -g botify -m 0600 "${REPO_DIR}/deploy/ec2/.env.example" "${APP_DIR}/.env"
else
  echo "Keeping existing ${APP_DIR}/.env (not overwritten)."
fi
if [[ ! -e "${APP_DIR}/ec2-agent/.env" ]]; then
  install -o botify -g botify -m 0600 "${APP_DIR}/ec2-agent/.env.example" "${APP_DIR}/ec2-agent/.env"
else
  echo "Keeping existing ${APP_DIR}/ec2-agent/.env (not overwritten)."
fi
install -o root -g root -m 0644 "${REPO_DIR}/deploy/ec2/systemd/"*.service /etc/systemd/system/
systemctl daemon-reload
echo "Installed. Review both .env files before running start.sh."
