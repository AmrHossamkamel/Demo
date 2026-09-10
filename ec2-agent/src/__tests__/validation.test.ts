import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  StartWorkloadRequestSchema,
  StopWorkloadRequestSchema,
  WorkloadParamsSchema,
} from "../workload/types";

describe("Zod Validation", () => {
  describe("StartWorkloadRequestSchema", () => {
    it("accepts valid CPU workload", () => {
      const result = StartWorkloadRequestSchema.safeParse({
        executionId: "test-001",
        workload: { type: "cpu", percent: 50, durationSec: 10 },
      });
      assert.ok(result.success);
    });

    it("rejects empty executionId", () => {
      const result = StartWorkloadRequestSchema.safeParse({
        executionId: "",
        workload: { type: "cpu", percent: 50, durationSec: 10 },
      });
      assert.ok(!result.success);
    });

    it("rejects executionId with unsafe characters", () => {
      const result = StartWorkloadRequestSchema.safeParse({
        executionId: "test/../../../etc",
        workload: { type: "cpu", percent: 50, durationSec: 10 },
      });
      assert.ok(!result.success);
    });

    it("rejects workload type not in enum", () => {
      const result = StartWorkloadRequestSchema.safeParse({
        executionId: "test-001",
        workload: { type: "invalid", percent: 50, durationSec: 10 },
      });
      assert.ok(!result.success);
    });
  });

  describe("CPU params", () => {
    it("rejects percent > 80", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "cpu",
        percent: 81,
        durationSec: 10,
      });
      assert.ok(!result.success);
    });

    it("rejects percent < 1", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "cpu",
        percent: 0,
        durationSec: 10,
      });
      assert.ok(!result.success);
    });

    it("rejects duration > 3600", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "cpu",
        percent: 50,
        durationSec: 3601,
      });
      assert.ok(!result.success);
    });
  });

  describe("Memory params", () => {
    it("rejects mb > 4096", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "memory",
        mb: 4097,
        durationSec: 10,
      });
      assert.ok(!result.success);
    });

    it("accepts valid memory params", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "memory",
        mb: 100,
        durationSec: 30,
      });
      assert.ok(result.success);
    });
  });

  describe("Disk params", () => {
    it("rejects mb > 1024", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "disk",
        mb: 1025,
        filename: "test.txt",
        durationSec: 10,
      });
      assert.ok(!result.success);
    });

    it("rejects unsafe filename", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "disk",
        mb: 10,
        filename: "../etc/passwd",
        durationSec: 10,
      });
      assert.ok(!result.success);
    });

    it("accepts valid disk params", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "disk",
        mb: 10,
        filename: "test-file_123.dat",
        durationSec: 5,
      });
      assert.ok(result.success);
    });
  });

  describe("Network params", () => {
    it("rejects requestsPerSec > 500", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "network",
        url: "https://example.com",
        requestsPerSec: 501,
        durationSec: 10,
      });
      assert.ok(!result.success);
    });

    it("rejects invalid URL", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "network",
        url: "not-a-url",
        requestsPerSec: 10,
        durationSec: 10,
      });
      assert.ok(!result.success);
    });
  });

  describe("HTTP params", () => {
    it("accepts valid HTTP params", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "http",
        url: "https://example.com/api",
        method: "POST",
        headers: { "X-Test": "value" },
        body: { key: "value" },
        requestsPerSec: 10,
        durationSec: 5,
      });
      assert.ok(result.success);
    });

    it("rejects invalid method", () => {
      const result = WorkloadParamsSchema.safeParse({
        type: "http",
        url: "https://example.com",
        method: "INVALID",
        requestsPerSec: 10,
        durationSec: 5,
      });
      assert.ok(!result.success);
    });
  });

  describe("StopWorkloadRequestSchema", () => {
    it("accepts valid stop request", () => {
      const result = StopWorkloadRequestSchema.safeParse({
        executionId: "test-001",
      });
      assert.ok(result.success);
    });

    it("rejects empty executionId", () => {
      const result = StopWorkloadRequestSchema.safeParse({
        executionId: "",
      });
      assert.ok(!result.success);
    });
  });
});
