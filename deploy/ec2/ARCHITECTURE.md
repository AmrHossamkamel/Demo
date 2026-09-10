# Architecture

The public request path is:

`client -> Nginx (443/TLS) -> 127.0.0.1:4100 -> FastAPI + static frontend`

The Node/TypeScript EC2 agent is a separate safety-bounded workload service on
localhost port 4200.
Its production entry point is `ec2-agent/dist/index.js`, built from
`ec2-agent/src` with `npm run build`. `botify-demo-agent.service` keeps it
bound to localhost; the backend reaches it through a configured target and
the backend agent token, never through browser code.

The Python app is launched from the repository root with
`/opt/botify-demo/.venv/bin/python /opt/botify-demo/run.py`. Persistent history,
target definitions, and logs live below `/opt/botify-demo/data`. systemd
provides restart, privilege separation, and journald logging.
