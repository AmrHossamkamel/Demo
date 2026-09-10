import * as fs from "fs";
import * as path from "path";
import { logger } from "../logger";
import {
  WorkloadParams,
  WorkloadType,
  WorkloadStatus,
  StartWorkloadResponse,
  StopWorkloadResponse,
  StopAllWorkloadsResponse,
} from "./types";
import { Config } from "../config";

interface RunningWorkload {
  executionId: string;
  type: WorkloadType;
  params: WorkloadParams;
  startedAt: Date;
  abortController: AbortController;
  timer: ReturnType<typeof setTimeout> | null;
}

export class WorkloadManager {
  private running = new Map<string, RunningWorkload>();
  private config: Config;

  constructor(config: Config) {
    this.config = config;
    this.ensureDiskDir();
  }

  private ensureDiskDir(): void {
    const dir = path.resolve(this.config.diskTempDir);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  start(executionId: string, params: WorkloadParams): StartWorkloadResponse {
    if (this.running.has(executionId)) {
      throw new Error(`Execution ID '${executionId}' is already running`);
    }

    // Synchronous validation for network/http workloads
    if (params.type === "network" || params.type === "http") {
      if (!this.isUrlAllowed(params.url)) {
        throw new Error(`URL '${params.url}' is not on the HTTP allow-list`);
      }
    }

    const abortController = new AbortController();
    const startedAt = new Date();

    const workload: RunningWorkload = {
      executionId,
      type: params.type,
      params,
      startedAt,
      abortController,
      timer: null,
    };

    this.running.set(executionId, workload);

    logger.info("Workload started", {
      executionId,
      type: params.type,
    });

    this.executeWorkload(workload).catch((err) => {
      logger.error("Workload execution error", {
        executionId,
        error: err instanceof Error ? err.message : String(err),
      });
      this.setStatus(workload, "error");
    });

    return {
      executionId,
      type: params.type,
      state: "running",
      message: `Workload ${params.type} started successfully`,
    };
  }

  private async executeWorkload(workload: RunningWorkload): Promise<void> {
    const signal = workload.abortController.signal;

    try {
      switch (workload.params.type) {
        case "cpu":
          await this.runCpuWorkload(workload, signal);
          break;
        case "memory":
          await this.runMemoryWorkload(workload, signal);
          break;
        case "disk":
          await this.runDiskWorkload(workload, signal);
          break;
        case "network":
          await this.runNetworkWorkload(workload, signal);
          break;
        case "http":
          await this.runHttpWorkload(workload, signal);
          break;
      }

      if (!signal.aborted) {
        this.setStatus(workload, "completed");
        logger.info("Workload completed", {
          executionId: workload.executionId,
          type: workload.type,
        });
      }
    } catch (err) {
      if (signal.aborted) {
        this.setStatus(workload, "stopped");
        logger.info("Workload stopped", { executionId: workload.executionId });
      } else {
        this.setStatus(workload, "error");
        logger.error("Workload failed", {
          executionId: workload.executionId,
          error: err instanceof Error ? err.message : String(err),
        });
      }
    } finally {
      this.cleanup(workload);
    }
  }

  private setStatus(workload: RunningWorkload, state: "completed" | "stopped" | "error"): void {
    (workload as any).state = state;
  }

  private cleanup(workload: RunningWorkload): void {
    if (workload.timer) {
      clearTimeout(workload.timer);
      workload.timer = null;
    }
    this.running.delete(workload.executionId);

    if (workload.params.type === "disk") {
      this.cleanupDiskFile(workload.params.filename);
    }
  }

  private cleanupDiskFile(filename: string): void {
    try {
      const filePath = path.resolve(this.config.diskTempDir, filename);
      const normalizedDir = path.resolve(this.config.diskTempDir);
      const normalizedFile = path.resolve(filePath);
      if (normalizedFile.startsWith(normalizedDir) && fs.existsSync(normalizedFile)) {
        fs.unlinkSync(normalizedFile);
        logger.info("Disk file cleaned up", { filename });
      }
    } catch (err) {
      logger.warn("Failed to cleanup disk file", {
        filename,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  private sleep(ms: number, signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }

      const onAbort = () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      };

      signal.addEventListener("abort", onAbort, { once: true });

      const timer = setTimeout(() => {
        signal.removeEventListener("abort", onAbort);
        resolve();
      }, ms);
    });
  }

  private async runCpuWorkload(workload: RunningWorkload, signal: AbortSignal): Promise<void> {
    const params = workload.params as { type: "cpu"; percent: number; durationSec: number };
    const targetPercent = Math.min(params.percent, this.config.limits.MAX_CPU_PERCENT);
    const durationMs = Math.min(
      params.durationSec * 1000,
      this.config.limits.MAX_DURATION_SEC * 1000
    );

    const intervalMs = 100;
    const busyMs = Math.floor((targetPercent / 100) * intervalMs);
    const idleMs = intervalMs - busyMs;

    const iterations = Math.ceil(durationMs / intervalMs);

    for (let i = 0; i < iterations; i++) {
      if (signal.aborted) break;

      const busyEnd = Date.now() + busyMs;
      while (Date.now() < busyEnd) {
        if (signal.aborted) break;
        Math.random();
      }

      if (idleMs > 0 && !signal.aborted) {
        await this.sleep(idleMs, signal);
      }
    }
  }

  private async runMemoryWorkload(workload: RunningWorkload, signal: AbortSignal): Promise<void> {
    const params = workload.params as { type: "memory"; mb: number; durationSec: number };
    const targetMb = Math.min(params.mb, this.config.limits.MAX_MEMORY_MB);
    const durationMs = Math.min(
      params.durationSec * 1000,
      this.config.limits.MAX_DURATION_SEC * 1000
    );

    const buffers: Buffer[] = [];
    const chunkSize = 1024 * 1024; // 1MB chunks
    const totalChunks = Math.floor(targetMb);

    for (let i = 0; i < totalChunks; i++) {
      if (signal.aborted) break;
      const buf = Buffer.alloc(chunkSize);
      for (let j = 0; j < chunkSize; j += 4096) {
        buf.writeUInt32LE(j, j);
      }
      buffers.push(buf);
    }

    await this.sleep(durationMs, signal);

    buffers.length = 0;
  }

  private async runDiskWorkload(workload: RunningWorkload, signal: AbortSignal): Promise<void> {
    const params = workload.params as {
      type: "disk";
      mb: number;
      filename: string;
      durationSec: number;
    };
    const targetMb = Math.min(params.mb, this.config.limits.MAX_DISK_MB);
    const durationMs = Math.min(
      params.durationSec * 1000,
      this.config.limits.MAX_DURATION_SEC * 1000
    );

    const dir = path.resolve(this.config.diskTempDir);
    const filePath = path.resolve(dir, params.filename);

    const normalizedDir = path.resolve(dir);
    if (!filePath.startsWith(normalizedDir)) {
      throw new Error("Path traversal detected");
    }

    this.ensureDiskDir();

    const chunkSize = 64 * 1024; // 64KB chunks
    const totalChunks = Math.ceil((targetMb * 1024 * 1024) / chunkSize);
    const chunk = Buffer.alloc(chunkSize, 0xab);

    const fd = fs.openSync(filePath, "w");
    try {
      for (let i = 0; i < totalChunks; i++) {
        if (signal.aborted) break;
        fs.writeSync(fd, chunk, 0, chunkSize);
      }
    } finally {
      fs.closeSync(fd);
    }

    await this.sleep(durationMs, signal);
  }

  private isUrlAllowed(urlStr: string): boolean {
    try {
      const url = new URL(urlStr);
      const hostname = url.hostname.toLowerCase();
      return this.config.httpAllowList.some((allowed) => {
        const allowedLower = allowed.toLowerCase();
        return hostname === allowedLower || hostname.endsWith("." + allowedLower);
      });
    } catch {
      return false;
    }
  }

  private async runNetworkWorkload(workload: RunningWorkload, signal: AbortSignal): Promise<void> {
    const params = workload.params as {
      type: "network";
      url: string;
      requestsPerSec: number;
      durationSec: number;
    };

    if (!this.isUrlAllowed(params.url)) {
      throw new Error(`URL '${params.url}' is not on the HTTP allow-list`);
    }

    const rate = Math.min(params.requestsPerSec, this.config.limits.MAX_EVENT_RATE);
    const durationMs = Math.min(
      params.durationSec * 1000,
      this.config.limits.MAX_DURATION_SEC * 1000
    );
    const intervalMs = 1000 / rate;

    const deadline = Date.now() + durationMs;

    while (Date.now() < deadline && !signal.aborted) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);

        await fetch(params.url, {
          method: "GET",
          signal: controller.signal,
        });

        clearTimeout(timeout);
      } catch {
        // Network errors are expected in stress testing
      }

      const nextTick = Date.now() + intervalMs;
      const sleepMs = Math.max(0, nextTick - Date.now());
      if (sleepMs > 0) {
        await this.sleep(sleepMs, signal);
      }
    }
  }

  private async runHttpWorkload(workload: RunningWorkload, signal: AbortSignal): Promise<void> {
    const params = workload.params as {
      type: "http";
      url: string;
      method: string;
      headers?: Record<string, string>;
      body?: unknown;
      requestsPerSec: number;
      durationSec: number;
    };

    if (!this.isUrlAllowed(params.url)) {
      throw new Error(`URL '${params.url}' is not on the HTTP allow-list`);
    }

    const rate = Math.min(params.requestsPerSec, this.config.limits.MAX_EVENT_RATE);
    const durationMs = Math.min(
      params.durationSec * 1000,
      this.config.limits.MAX_DURATION_SEC * 1000
    );
    const intervalMs = 1000 / rate;

    const deadline = Date.now() + durationMs;

    while (Date.now() < deadline && !signal.aborted) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);

        const fetchOptions: RequestInit = {
          method: params.method,
          signal: controller.signal,
          headers: params.headers,
        };

        if (params.body && ["POST", "PUT", "PATCH"].includes(params.method)) {
          fetchOptions.body = JSON.stringify(params.body);
          (fetchOptions.headers as Record<string, string>)["Content-Type"] = "application/json";
        }

        await fetch(params.url, fetchOptions);

        clearTimeout(timeout);
      } catch {
        // Errors expected in stress testing
      }

      const nextTick = Date.now() + intervalMs;
      const sleepMs = Math.max(0, nextTick - Date.now());
      if (sleepMs > 0) {
        await this.sleep(sleepMs, signal);
      }
    }
  }

  stop(executionId: string): StopWorkloadResponse {
    const workload = this.running.get(executionId);
    if (!workload) {
      throw new Error(`No running workload found with execution ID '${executionId}'`);
    }

    workload.abortController.abort();
    this.running.delete(executionId);

    logger.info("Workload stop requested", { executionId });

    return {
      executionId,
      state: "stopped",
      message: `Workload ${executionId} stop requested`,
    };
  }

  stopAll(): StopAllWorkloadsResponse {
    const count = this.running.size;
    for (const [id, workload] of this.running) {
      workload.abortController.abort();
      logger.info("Workload stop-all", { executionId: id });
    }
    this.running.clear();

    return {
      stopped: count,
      message: `Stopped ${count} running workload(s)`,
    };
  }

  getRunning(): WorkloadStatus[] {
    const statuses: WorkloadStatus[] = [];
    for (const [, workload] of this.running) {
      const elapsed = (Date.now() - workload.startedAt.getTime()) / 1000;
      statuses.push({
        executionId: workload.executionId,
        type: workload.type,
        state: "running",
        startedAt: workload.startedAt.toISOString(),
        elapsed: Math.round(elapsed * 100) / 100,
        params: workload.params,
      });
    }
    return statuses;
  }

  getRunningCount(): number {
    return this.running.size;
  }

  async shutdown(): Promise<void> {
    this.stopAll();
    // Clean up disk temp directory
    try {
      const dir = path.resolve(this.config.diskTempDir);
      if (fs.existsSync(dir)) {
        const files = fs.readdirSync(dir);
        for (const file of files) {
          const filePath = path.join(dir, file);
          if (fs.statSync(filePath).isFile()) {
            fs.unlinkSync(filePath);
          }
        }
      }
    } catch (err) {
      logger.warn("Failed to cleanup disk directory on shutdown", {
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }
}
