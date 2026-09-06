import { describe, expect, it } from "vitest";
import { withQuery, withRepoPath } from "./api";

describe("withRepoPath", () => {
  it("leaves unscoped API paths unchanged", () => {
    expect(withRepoPath("/api/overview")).toBe("/api/overview");
  });

  it("encodes repository paths with spaces", () => {
    expect(withRepoPath("/api/graph", "/Users/me/Codes/Codebase Catographer/app")).toBe(
      "/api/graph?repo_path=%2FUsers%2Fme%2FCodes%2FCodebase+Catographer%2Fapp"
    );
  });
});

describe("withQuery", () => {
  it("omits empty optional values", () => {
    expect(withQuery("/api/graph", { repo_path: undefined, limit: 160 })).toBe(
      "/api/graph?limit=160"
    );
  });

  it("combines repo scope and graph limits", () => {
    expect(withQuery("/api/graph", { repo_path: "/repo", limit: 160, edge_limit: 400 })).toBe(
      "/api/graph?repo_path=%2Frepo&limit=160&edge_limit=400"
    );
  });
});
