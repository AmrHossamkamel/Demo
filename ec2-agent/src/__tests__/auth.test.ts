import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { constantTimeCompare } from "../auth";

describe("constantTimeCompare", () => {
  it("returns true for equal strings", () => {
    assert.ok(constantTimeCompare("abc", "abc"));
  });

  it("returns false for different strings of same length", () => {
    assert.ok(!constantTimeCompare("abc", "abd"));
  });

  it("returns false for different length strings", () => {
    assert.ok(!constantTimeCompare("abc", "abcd"));
  });

  it("returns true for empty strings", () => {
    assert.ok(constantTimeCompare("", ""));
  });

  it("returns false when one is empty", () => {
    assert.ok(!constantTimeCompare("", "a"));
  });
});
