import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { WorkloadManager } from "../workload/manager";
import { Config } from "../config";

function createTestConfig(): Config {
  return {
    host: "127.0.0.1",
    port: 0,
    authToken: "test-secret-token-12345",
    corsOrigins: ["http://localhost:3000"],
    diskTempDir: "./tmp-test-health",
    diskHardCapMb: 1024,
    httpAllowList: [],
    logLevel: "error",
    limits: {
      MAX_CPU_PERCENT: 80,
      MAX_MEMORY_MB: 4096,
      MAX_DURATION_SEC: 3600,
      MAX_EVENT_RATE: 500,
      MAX_DISK_MB: 1024,
    },
  };
}

function makeRequest(
  port: number,
  path: string,
  options: { method?: string; headers?: Record<string, string>; body?: unknown } = {}
): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const { method = "GET", headers = {}, body } = options;
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port,
        path,
        method,
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          let parsed: unknown;
          try {
            parsed = JSON.parse(data);
          } catch {
            parsed = data;
          }
          resolve({ status: res.statusCode ?? 0, body: parsed });
        });
      }
    );
    req.on("error", reject);
    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

describe("HTTP Endpoints", () => {
  let server: http.Server;
  let port: number;

  beforeEach(async () => {
    const config = createTestConfig();
    const manager = new WorkloadManager(config);

    const express = await import("express");
    const app = express.default();
    app.use(express.default.json());

    // Health route (public)
    app.get("/health", (_req, res) => {
      res.json({ status: "ok", running: manager.getRunningCount() });
    });

    // Auth middleware for protected routes
    app.use("/api", (req, res, next) => {
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith("Bearer ")) {
        res.status(401).json({ error: "Missing or malformed Authorization header" });
        return;
      }
      const token = authHeader.slice(7);
      if (token !== config.authToken) {
        res.status(403).json({ error: "Invalid authentication token" });
        return;
      }
      next();
    });

    // Protected workload routes
    app.post("/api/workload/start", (req, res) => {
      try {
        const { executionId, workload } = req.body;
        const result = manager.start(executionId, workload);
        res.status(201).json(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        res.status(409).json({ error: message });
      }
    });

    app.get("/api/workload/running", (_req, res) => {
      res.json({ running: manager.getRunning(), count: manager.getRunningCount() });
    });

    server = app.listen(0, "127.0.0.1");
    await new Promise<void>((resolve) => server.on("listening", resolve));
    const addr = server.address();
    port = typeof addr === "object" && addr ? addr.port : 0;
  });

  afterEach(async () => {
    if (server) {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });

  it("GET /health returns 200", async () => {
    const res = await makeRequest(port, "/health");
    assert.equal(res.status, 200);
    assert.equal((res.body as any).status, "ok");
  });

  it("GET /api/workload/running without auth returns 401", async () => {
    const res = await makeRequest(port, "/api/workload/running");
    assert.equal(res.status, 401);
  });

  it("GET /api/workload/running with wrong token returns 403", async () => {
    const res = await makeRequest(port, "/api/workload/running", {
      headers: { Authorization: "Bearer wrong-token" },
    });
    assert.equal(res.status, 403);
  });

  it("GET /api/workload/running with valid token returns 200", async () => {
    const res = await makeRequest(port, "/api/workload/running", {
      headers: { Authorization: "Bearer test-secret-token-12345" },
    });
    assert.equal(res.status, 200);
    assert.equal((res.body as any).count, 0);
  });

  it("POST /api/workload/start with valid request returns 201", async () => {
    const res = await makeRequest(port, "/api/workload/start", {
      method: "POST",
      headers: { Authorization: "Bearer test-secret-token-12345" },
      body: {
        executionId: "test-start-001",
        workload: { type: "cpu", percent: 10, durationSec: 1 },
      },
    });
    assert.equal(res.status, 201);
    assert.equal((res.body as any).executionId, "test-start-001");
    assert.equal((res.body as any).state, "running");
  });

  it("POST /api/workload/start without auth returns 401", async () => {
    const res = await makeRequest(port, "/api/workload/start", {
      method: "POST",
      body: {
        executionId: "test-start-002",
        workload: { type: "cpu", percent: 10, durationSec: 1 },
      },
    });
    assert.equal(res.status, 401);
  });
});
