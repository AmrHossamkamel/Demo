import express from "express";
import helmet from "helmet";
import cors from "cors";
import { loadConfig, Config } from "./config";
import { logger, setLogLevel, sanitizeForLog } from "./logger";
import { createAuthMiddleware } from "./auth";
import { WorkloadManager } from "./workload/manager";
import { createHealthRouter } from "./routes/health";
import { createWorkloadRouter } from "./routes/workload";
import { createHttpInjectRouter } from "./routes/http";

interface AppContext {
  app: express.Application;
  manager: WorkloadManager;
}

function createApp(config: Config): AppContext {
  const app = express();

  app.use(helmet());
  app.use(
    cors({
      origin: config.corsOrigins,
      methods: ["GET", "POST"],
      allowedHeaders: ["Content-Type", "Authorization"],
    })
  );
  app.use(express.json({ limit: "1mb" }));

  const manager = new WorkloadManager(config);

  app.use(createHealthRouter(manager));

  const authMiddleware = createAuthMiddleware(config.authToken);
  app.use("/api", authMiddleware);
  app.use(createWorkloadRouter(manager));
  app.use(createHttpInjectRouter(config));

  app.use(
    (err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
      logger.error("Unhandled error", sanitizeForLog({ error: err.message }));
      res.status(500).json({ error: "Internal server error" });
    }
  );

  return { app, manager };
}

async function main(): Promise<void> {
  const config = loadConfig();
  setLogLevel(config.logLevel);

  logger.info("Starting EC2 Botify Demo Agent", {
    host: config.host,
    port: config.port,
    limits: config.limits,
    httpAllowList: config.httpAllowList,
  });

  const { app, manager } = createApp(config);

  const server = app.listen(config.port, config.host, () => {
    logger.info("Agent listening", {
      address: `http://${config.host}:${config.port}`,
    });
  });

  const shutdown = async (signal: string) => {
    logger.info("Shutdown signal received", { signal });
    await manager.shutdown();
    server.close(() => {
      logger.info("Server closed");
      process.exit(0);
    });

    setTimeout(() => {
      logger.error("Forced shutdown after timeout");
      process.exit(1);
    }, 5000);
  };

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

main().catch((err) => {
  logger.error("Fatal startup error", { error: err.message });
  process.exit(1);
});
