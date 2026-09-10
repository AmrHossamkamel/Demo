import { Router, Request, Response } from "express";
import { WorkloadManager } from "../workload/manager";
import { validateBody } from "../middleware/validate";
import {
  StartWorkloadRequestSchema,
  StopWorkloadRequestSchema,
} from "../workload/types";

export function createWorkloadRouter(manager: WorkloadManager): Router {
  const router = Router();

  router.post(
    "/api/workload/start",
    validateBody(StartWorkloadRequestSchema),
    (req: Request, res: Response) => {
      try {
        const { executionId, workload } = req.body;
        const result = manager.start(executionId, workload);
        res.status(201).json(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        if (message.includes("already running")) {
          res.status(409).json({ error: message });
        } else {
          res.status(500).json({ error: "Internal server error" });
        }
      }
    }
  );

  router.post(
    "/api/workload/stop",
    validateBody(StopWorkloadRequestSchema),
    (req: Request, res: Response) => {
      try {
        const { executionId } = req.body;
        const result = manager.stop(executionId);
        res.json(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        if (message.includes("No running workload")) {
          res.status(404).json({ error: message });
        } else {
          res.status(500).json({ error: "Internal server error" });
        }
      }
    }
  );

  router.post("/api/workload/stop-all", (_req: Request, res: Response) => {
    const result = manager.stopAll();
    res.json(result);
  });

  router.get("/api/workload/running", (_req: Request, res: Response) => {
    const running = manager.getRunning();
    res.json({
      running,
      count: running.length,
    });
  });

  return router;
}
