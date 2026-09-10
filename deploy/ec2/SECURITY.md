# Security

- Run both services as the dedicated, non-login `botify` user.
- Keep application and agent ports bound to localhost. Permit public traffic
  only to Nginx 443 (and 80 only for an intentional ACME challenge).
- Configure Nginx `allow`/`deny` rules for trusted source CIDRs; do not use
  `0.0.0.0/0` for the administrative/demo interface.
- Use a long random `BOTIFY_AGENT_TOKEN` and keep it only in root-readable
  server-side `.env` files. The frontend must never collect or render it.
- Use HTTPS with a valid certificate and disable plain HTTP after certificate
  provisioning unless redirecting it to HTTPS.
- Keep `HTTP_ALLOW_LIST` narrow for agent network workloads and review
  `CORS_ORIGINS` before exposing the UI.
- Review `journalctl` and Nginx logs for failed authentication and unexpected
  source addresses. Rotate logs using the host's journald/logrotate policy.
- Back up configuration and data securely; do not include `.env`, tokens, or
  TLS private keys in releases or source control.

