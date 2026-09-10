import * as fs from "fs";
import * as path from "path";

const HARDCODED_LIMITS = {
  MAX_CPU_PERCENT: 80,
  MAX_MEMORY_MB: 4096,
  MAX_DURATION_SEC: 3600,
  MAX_EVENT_RATE: 500,
  MAX_DISK_MB: 1024,
} as const;

export type HardLimits = typeof HARDCODED_LIMITS;

function loadEnvFile(): void {
  const envPath = path.resolve(__dirname, "..", ".env");
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, "utf-8").split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      const val = trimmed.slice(eqIdx + 1).trim();
      if (!(key in process.env)) {
        process.env[key] = val;
      }
    }
  }
}

loadEnvFile();

export interface Config {
  host: string;
  port: number;
  authToken: string;
  corsOrigins: string[];
  diskTempDir: string;
  diskHardCapMb: number;
  httpAllowList: string[];
  logLevel: string;
  limits: HardLimits;
}

function requireEnv(name: string, fallback?: string): string {
  const val = process.env[name] ?? fallback;
  if (val === undefined || val === "") {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return val;
}

export function loadConfig(): Config {
  return {
    host: process.env.HOST ?? "127.0.0.1",
    port: parseInt(process.env.PORT ?? "4100", 10),
    authToken: requireEnv("AGENT_AUTH_TOKEN", "CHANGE_ME_TO_A_SECURE_RANDOM_TOKEN"),
    corsOrigins: (process.env.CORS_ORIGINS ?? "http://localhost:3000")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    diskTempDir: process.env.DISK_TEMP_DIR ?? "./tmp-workloads",
    diskHardCapMb: Math.min(
      parseInt(process.env.DISK_HARD_CAP_MB ?? String(HARDCODED_LIMITS.MAX_DISK_MB), 10),
      HARDCODED_LIMITS.MAX_DISK_MB
    ),
    httpAllowList: (process.env.HTTP_ALLOW_LIST ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    logLevel: process.env.LOG_LEVEL ?? "info",
    limits: { ...HARDCODED_LIMITS },
  };
}

export const LIMITS = HARDCODED_LIMITS;
