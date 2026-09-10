import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { WorkloadManager } from "../workload/manager";
import { Config } from "../config";

function createTestConfig(): Config {
  return {
    host: "127.0.0.1",
    port: 4100,
    authToken: "test-token",
    corsOrigins: ["http://localhost:3000"],
    diskTempDir: "./tmp-test-workloads",
    diskHardCapMb: 1024,
    httpAllowList: ["example.com", "httpbin.org"],
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

describe("WorkloadManager", () => {
  let manager: WorkloadManager;

  beforeEach(() => {
    manager = new WorkloadManager(createTestConfig());
  });

  describe("Duplicate execution IDs", () => {
    it("rejects duplicate execution IDs", () => {
      manager.start("dup-001", { type: "cpu", percent: 10, durationSec: 60 });

      assert.throws(
        () => manager.start("dup-001", { type: "cpu", percent: 10, durationSec: 60 }),
        /already running/
      );
    });

    it("allows same ID after workload completes", async () => {
      manager.start("recycle-001", { type: "cpu", percent: 10, durationSec: 1 });
      // Wait for completion
      await new Promise((resolve) => setTimeout(resolve, 1500));

      const result = manager.start("recycle-001", { type: "cpu", percent: 10, durationSec: 1 });
      assert.equal(result.executionId, "recycle-001");
      assert.equal(result.state, "running");
    });
  });

  describe("Stop workload", () => {
    it("stops a running workload", () => {
      manager.start("stop-001", { type: "cpu", percent: 10, durationSec: 60 });
      const result = manager.stop("stop-001");
      assert.equal(result.executionId, "stop-001");
      assert.equal(result.state, "stopped");
    });

    it("throws for non-existent workload", () => {
      assert.throws(
        () => manager.stop("nonexistent"),
        /No running workload/
      );
    });
  });

  describe("Stop all workloads", () => {
    it("stops all running workloads", () => {
      manager.start("all-001", { type: "cpu", percent: 10, durationSec: 60 });
      manager.start("all-002", { type: "cpu", percent: 10, durationSec: 60 });
      manager.start("all-003", { type: "cpu", percent: 10, durationSec: 60 });

      const result = manager.stopAll();
      assert.equal(result.stopped, 3);

      const running = manager.getRunning();
      assert.equal(running.length, 0);
    });

    it("returns 0 when no workloads running", () => {
      const result = manager.stopAll();
      assert.equal(result.stopped, 0);
    });
  });

  describe("Get running workloads", () => {
    it("returns empty array when nothing running", () => {
      const running = manager.getRunning();
      assert.equal(running.length, 0);
    });

    it("returns running workloads", () => {
      manager.start("run-001", { type: "cpu", percent: 10, durationSec: 60 });
      manager.start("run-002", { type: "memory", mb: 10, durationSec: 60 });

      const running = manager.getRunning();
      assert.equal(running.length, 2);
      assert.ok(running.some((w) => w.executionId === "run-001"));
      assert.ok(running.some((w) => w.executionId === "run-002"));
    });
  });

  describe("Cancellation", () => {
    it("cancels a running CPU workload", async () => {
      manager.start("cancel-001", { type: "cpu", percent: 50, durationSec: 30 });
      await new Promise((resolve) => setTimeout(resolve, 100));

      const result = manager.stop("cancel-001");
      assert.equal(result.state, "stopped");

      await new Promise((resolve) => setTimeout(resolve, 100));
      const running = manager.getRunning();
      assert.equal(running.length, 0);
    });
  });

  describe("Limits enforcement", () => {
    it("creates workload with percent at limit", () => {
      const result = manager.start("limit-001", { type: "cpu", percent: 80, durationSec: 10 });
      assert.equal(result.state, "running");
    });

    it("creates memory workload at limit", () => {
      const result = manager.start("limit-002", { type: "memory", mb: 4096, durationSec: 10 });
      assert.equal(result.state, "running");
    });
  });
});
