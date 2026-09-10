# Botify Demo EC2 deployment

These assets install the repository under `/opt/botify-demo` as the unprivileged
`botify` user. The FastAPI application listens only on `127.0.0.1:4100`; Nginx
is the public HTTPS reverse proxy. The optional EC2 agent listens on
`127.0.0.1:4200` so it does not conflict with the FastAPI application; remote
target definitions should use that port.

## Prerequisites

- Ubuntu 22.04/24.04 or Amazon Linux 2023
- Node.js 20 or newer and npm
- Python 3.10 or newer, `python3-venv`, and a compiler suitable for Python wheels
- Nginx and an existing TLS certificate (for example, Certbot-managed)
- A trusted-source CIDR for the Nginx security group and application access

## Install and configure

From the repository root:

```bash
sudo deploy/ec2/scripts/install.sh
sudo deploy/ec2/scripts/configure.sh
sudoedit /opt/botify-demo/.env
sudoedit /opt/botify-demo/ec2-agent/.env
sudo deploy/ec2/scripts/start.sh
```

`install.sh` installs dependencies and creates configuration files only when
they do not exist. It never replaces a populated `.env`. `configure.sh` makes a
timestamped backup before an explicit `--force` replacement. Set unique
credentials before starting services.

Copy `nginx/botify-agent.conf` to `/etc/nginx/sites-available/`, replace the
server name and certificate paths, restrict `allow`/`deny` to trusted source
networks, enable the site, and reload Nginx. Do not expose ports 4100 or 4200
to the internet.

## Operations

```bash
sudo deploy/ec2/scripts/health-check.sh
sudo systemctl status botify-demo-app botify-demo-agent
sudo journalctl -u botify-demo-app -u botify-demo-agent -f
sudo deploy/ec2/scripts/stop.sh
```

For updates, deploy a reviewed release into `/opt/botify-demo`, run the
dependency/build portions of `install.sh`, then restart with `start.sh`.
Back up `.env`, `data/`, and the target store before upgrades.

## Uninstall

`sudo deploy/ec2/scripts/uninstall.sh` stops and disables both services,
removes their unit files and the Nginx site, and leaves `/opt/botify-demo`
untouched unless `--purge` is supplied. `--purge` is destructive and requires
an explicit second confirmation flag: `--purge --yes`.
