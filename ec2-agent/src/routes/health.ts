import { Router, Request, Response } from "express";
import { WorkloadManager } from "../workload/manager";

export function createHealthRouter(manager: WorkloadManager): Router {
  const router = Router();

  router.get("/health", (_req: Request, res: Response) => {
    res.json({
      status: "ok",
      timestamp: new Date().toISOString(),
      running: manager.getRunningCount(),
    });
  });

  return router;
}
