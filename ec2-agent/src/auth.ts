import * as crypto from "crypto";
import { Request, Response, NextFunction } from "express";

export function constantTimeCompare(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) {
    return false;
  }
  return crypto.timingSafeEqual(bufA, bufB);
}

export function createAuthMiddleware(validToken: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      res.status(401).json({ error: "Missing or malformed Authorization header" });
      return;
    }
    const token = authHeader.slice(7);
    if (!constantTimeCompare(token, validToken)) {
      res.status(403).json({ error: "Invalid authentication token" });
      return;
    }
    next();
  };
}
