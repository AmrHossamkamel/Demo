import { Router, Request, Response } from "express";
import { z } from "zod";
import { validateBody } from "../middleware/validate";
import { Config } from "../config";

const HttpInjectSchema = z.object({
  url: z.string().url(),
  method: z.enum(["GET", "POST", "PUT", "DELETE", "PATCH"]).default("GET"),
  headers: z.record(z.string()).optional(),
  body: z.unknown().optional(),
  timeoutMs: z.number().min(1000).max(30000).default(5000),
});

export function createHttpInjectRouter(config: Config): Router {
  const router = Router();

  router.post(
    "/api/http/inject",
    validateBody(HttpInjectSchema),
    async (req: Request, res: Response) => {
      const { url, method, headers, body, timeoutMs } = req.body;

      try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname.toLowerCase();

        const allowed = config.httpAllowList.some((allowed) => {
          const allowedLower = allowed.toLowerCase();
          return hostname === allowedLower || hostname.endsWith("." + allowedLower);
        });

        if (!allowed) {
          res.status(403).json({
            error: `URL '${url}' is not on the HTTP allow-list`,
          });
          return;
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);

        const fetchOptions: RequestInit = {
          method,
          signal: controller.signal,
          headers,
        };

        if (body && ["POST", "PUT", "PATCH"].includes(method)) {
          fetchOptions.body = JSON.stringify(body);
          (fetchOptions.headers as Record<string, string>)["Content-Type"] = "application/json";
        }

        const response = await fetch(url, fetchOptions);
        clearTimeout(timeout);

        let responseBody: unknown;
        const contentType = response.headers.get("content-type") ?? "";
        if (contentType.includes("application/json")) {
          responseBody = await response.json();
        } else {
          responseBody = await response.text();
        }

        res.json({
          status: response.status,
          statusText: response.statusText,
          headers: Object.fromEntries(response.headers.entries()),
          body: responseBody,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        res.status(502).json({ error: `HTTP request failed: ${message}` });
      }
    }
  );

  return router;
}
