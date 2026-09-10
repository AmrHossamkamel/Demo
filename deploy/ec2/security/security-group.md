# EC2 security-group guidance

Allow inbound traffic only as follows:

| Port | Source | Purpose |
| --- | --- | --- |
| 443/tcp | trusted office/VPN CIDRs | Nginx HTTPS UI/API |
| 80/tcp | trusted CIDRs, temporarily | ACME challenge or HTTPS redirect |
| 22/tcp | bastion/administrator CIDRs | SSH administration |

Do not allow 4100 (FastAPI) or 4200 (agent) from the internet. If a remote
controller must reach an agent on another instance, allow the agent port only
from the controller's security group, use HTTPS, and keep the token in the
server-side environment. Egress should be limited to required observability
services and explicitly allow-listed workload destinations.

