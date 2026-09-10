import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { WorkloadManager } from "../workload/manager";
import { Config } from "../config";

function createTestConfig(allowList: string[] = ["example.com"]): Config {
  return {
    host: "127.0.0.1",
    port: 4100,
    authToken: "test-token",
    corsOrigins: ["http://localhost:3000"],
    diskTempDir: "./tmp-test-workloads",
    diskHardCapMb: 1024,
    httpAllowList: allowList,
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

describe("HTTP Allow-list", () => {
  it("rejects network workload for URL not on allow-list", async () => {
    const manager = new WorkloadManager(createTestConfig(["example.com"]));

    assert.throws(
      () =>
        manager.start("bad-url", {
          type: "network",
          url: "https://evil.com/attack",
          requestsPerSec: 10,
          durationSec: 10,
        }),
      /not on the HTTP allow-list/
    );
  });

  it("allows network workload for URL on allow-list", () => {
    const manager = new WorkloadManager(createTestConfig(["example.com"]));

    const result = manager.start("good-url", {
      type: "network",
      url: "https://example.com/api",
      requestsPerSec: 1,
      durationSec: 1,
    });

    assert.equal(result.state, "running");
    manager.stop("good-url");
  });

  it("allows subdomain of allowed host", () => {
    const manager = new WorkloadManager(createTestConfig(["example.com"]));

    const result = manager.start("sub-url", {
      type: "network",
      url: "https://api.example.com/v1",
      requestsPerSec: 1,
      durationSec: 1,
    });

    assert.equal(result.state, "running");
    manager.stop("sub-url");
  });

  it("rejects http workload for URL not on allow-list", async () => {
    const manager = new WorkloadManager(createTestConfig(["example.com"]));

    assert.throws(
      () =>
        manager.start("bad-http", {
          type: "http",
          url: "https://malicious.com/data",
          method: "GET",
          requestsPerSec: 10,
          durationSec: 10,
        }),
      /not on the HTTP allow-list/
    );
  });

  it("rejects IP address URLs that are not hostnames", async () => {
    const manager = new WorkloadManager(createTestConfig(["example.com"]));

    assert.throws(
      () =>
        manager.start("ip-url", {
          type: "network",
          url: "http://192.168.1.1/admin",
          requestsPerSec: 10,
          durationSec: 10,
        }),
      /not on the HTTP allow-list/
    );
  });
});
