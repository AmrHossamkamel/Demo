import { z } from "zod";

export const WorkloadTypeSchema = z.enum(["cpu", "memory", "disk", "network", "http"]);
export type WorkloadType = z.infer<typeof WorkloadTypeSchema>;

export const CpuParamsSchema = z.object({
  type: z.literal("cpu"),
  percent: z.number().min(1).max(80).describe("CPU usage percent (1-80)"),
  durationSec: z.number().min(1).max(3600).describe("Duration in seconds"),
});

export const MemoryParamsSchema = z.object({
  type: z.literal("memory"),
  mb: z.number().min(1).max(4096).describe("Memory allocation in MB"),
  durationSec: z.number().min(1).max(3600).describe("Duration in seconds"),
});

export const DiskParamsSchema = z.object({
  type: z.literal("disk"),
  mb: z.number().min(1).max(1024).describe("Disk write size in MB"),
  filename: z.string().min(1).max(255).regex(/^[a-zA-Z0-9._-]+$/, "Filename must be safe"),
  durationSec: z.number().min(1).max(3600).describe("Duration in seconds"),
});

export const NetworkParamsSchema = z.object({
  type: z.literal("network"),
  url: z.string().url().describe("Target URL (must be on allow-list)"),
  requestsPerSec: z.number().min(1).max(500).describe("Request rate"),
  durationSec: z.number().min(1).max(3600).describe("Duration in seconds"),
});

export const HttpParamsSchema = z.object({
  type: z.literal("http"),
  url: z.string().url().describe("Target URL (must be on allow-list)"),
  method: z.enum(["GET", "POST", "PUT", "DELETE", "PATCH"]).default("GET"),
  headers: z.record(z.string()).optional(),
  body: z.unknown().optional(),
  requestsPerSec: z.number().min(1).max(500).describe("Request rate"),
  durationSec: z.number().min(1).max(3600).describe("Duration in seconds"),
});

export const WorkloadParamsSchema = z.discriminatedUnion("type", [
  CpuParamsSchema,
  MemoryParamsSchema,
  DiskParamsSchema,
  NetworkParamsSchema,
  HttpParamsSchema,
]);

export type WorkloadParams = z.infer<typeof WorkloadParamsSchema>;
export type CpuParams = z.infer<typeof CpuParamsSchema>;
export type MemoryParams = z.infer<typeof MemoryParamsSchema>;
export type DiskParams = z.infer<typeof DiskParamsSchema>;
export type NetworkParams = z.infer<typeof NetworkParamsSchema>;
export type HttpParams = z.infer<typeof HttpParamsSchema>;

export interface StartWorkloadRequest {
  executionId: string;
  workload: WorkloadParams;
}

export const StartWorkloadRequestSchema = z.object({
  executionId: z.string().min(1).max(128).regex(/^[a-zA-Z0-9._-]+$/, "executionId must be safe"),
  workload: WorkloadParamsSchema,
});

export interface StopWorkloadRequest {
  executionId: string;
}

export const StopWorkloadRequestSchema = z.object({
  executionId: z.string().min(1).max(128),
});

export interface WorkloadStatus {
  executionId: string;
  type: WorkloadType;
  state: "running" | "completed" | "stopped" | "error";
  startedAt: string;
  elapsed: number;
  params: WorkloadParams;
}

export interface StartWorkloadResponse {
  executionId: string;
  type: WorkloadType;
  state: "running";
  message: string;
}

export interface StopWorkloadResponse {
  executionId: string;
  state: "stopped";
  message: string;
}

export interface StopAllWorkloadsResponse {
  stopped: number;
  message: string;
}

export interface RunningWorkloadsResponse {
  running: WorkloadStatus[];
  count: number;
}

export interface ErrorResponse {
  error: string;
  details?: unknown;
}
