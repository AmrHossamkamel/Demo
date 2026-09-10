# EC2 Botify Demo Agent

An independently runnable Node/TypeScript agent for executing safety-bounded workload requests on EC2. Designed to receive authenticated requests from a local controller and execute controlled stress-testing workloads.

## Features

- **Express HTTP server** with Helmet/CORS security, JSON body limits
- **Token authentication** with constant-time comparison for protected routes
- **Workload types**: CPU, Memory, Disk, Network, HTTP
- **Hard safety limits** enforced at the agent level
- **Graceful shutdown** on SIGTERM/SIGINT with cleanup
- **Structured logging** excluding secrets
- **Request validation** with Zod schemas

## Architecture

```
ec2-agent/
├── src/
│   ├── index.ts          # Express server entry point
│   ├── config.ts         # Configuration and hard limits
│   ├── logger.ts         # Structured logging
│   ├── auth.ts           # Token authentication middleware
│   ├── middleware/
│   │   └── validate.ts   # Zod validation middleware
│   ├── routes/
│   │   ├── health.ts     # GET /health (public)
│   │   ├── workload.ts   # Workload management routes
│   │   └── http.ts       # HTTP inject route
│   ├── workload/
│   │   ├── types.ts      # Request/response types and Zod schemas
│   │   └── manager.ts    # WorkloadManager with executors
│   └── __tests__/        # Unit tests
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Quick Start

```bash
# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env

# Edit .env and set a secure AGENT_AUTH_TOKEN

# Typecheck
npm run typecheck

# Run tests
npm test

# Build
npm run build

# Start production server
npm start

# Or start development (with ts-node)
npm run dev
```

## Configuration

Environment variables (set in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Bind address (never bind to 0.0.0.0 by default) |
| `PORT` | `4100` | Server port |
| `AGENT_AUTH_TOKEN` | (required) | Bearer token for authentication |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `DISK_TEMP_DIR` | `./tmp-workloads` | Temporary directory for disk workloads |
| `DISK_HARD_CAP_MB` | `1024` | Maximum disk write size in MB |
| `HTTP_ALLOW_LIST` | (empty) | Comma-separated allowed hostnames |
| `LOG_LEVEL` | `info` | Log level: debug, info, warn, error |

## API Endpoints

### Public

- `GET /health` - Health check (returns status and running workload count)

### Protected (requires `Authorization: Bearer <token>`)

- `POST /api/workload/start` - Start a new workload
- `POST /api/workload/stop` - Stop a specific workload
- `POST /api/workload/stop-all` - Stop all running workloads
- `GET /api/workload/running` - List running workloads
- `POST /api/http/inject` - Inject HTTP requests to allowed targets

## Hard Limits (Enforced)

| Limit | Value | Description |
|-------|-------|-------------|
| `MAX_CPU_PERCENT` | 80 | Maximum CPU duty cycle |
| `MAX_MEMORY_MB` | 4096 | Maximum memory allocation |
| `MAX_DURATION_SEC` | 3600 | Maximum workload duration |
| `MAX_EVENT_RATE` | 500 | Maximum requests per second |
| `MAX_DISK_MB` | 1024 | Maximum disk write size |

## Workload Types

### CPU
- Duty cycle simulation (busy/idle intervals)
- Bounded by MAX_CPU_PERCENT and MAX_DURATION_SEC

### Memory
- Allocates bounded buffer chunks
- Automatically freed on completion or cancellation

### Disk
- Writes to configured temp directory only
- Path traversal protection
- Automatic cleanup on completion

### Network
- HTTP GET requests to configured allow-list
- Rate and duration bounded
- AbortController-style cancellation

### HTTP
- Full HTTP method support (GET, POST, PUT, DELETE, PATCH)
- Custom headers and body support
- Rate and duration bounded

## Security

- **Authentication**: Bearer token with constant-time comparison
- **CORS**: Restricted to configured origins
- **Helmet**: Security headers enabled
- **Validation**: All inputs validated with Zod
- **Path traversal**: Disk workload filenames validated
- **Allow-list**: Network/HTTP workloads restricted to configured hosts
- **No secrets in logs**: Sensitive values redacted

## TLS Termination

This agent does not implement TLS. Use a reverse proxy (nginx, Caddy, etc.) to terminate TLS in front of this agent.

## Deployment

For EC2 deployment:
1. Install Node.js 20+
2. Copy `ec2-agent/` to the instance
3. Run `npm install && npm run build`
4. Configure `.env` with secure token
5. Start with `npm start`
6. Use a reverse proxy for TLS termination

## Testing

Tests use Node.js built-in test runner and do not require external services:

```bash
npm test
```

Test coverage includes:
- Health endpoint
- Authentication and rejection
- Request validation and limits
- Duplicate execution ID prevention
- Workload cancellation
- Stop-all functionality
- HTTP allow-list enforcement
