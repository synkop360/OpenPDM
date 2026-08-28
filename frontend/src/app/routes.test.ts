import { describe, expect, it } from "vitest";
import { parseAppRoute, projectAssetPath } from "./routes";

describe("parseAppRoute", () => {
  it("parses project routes and known tabs", () => {
    expect(parseAppRoute("/projects/project-7/assets")).toEqual({
      view: "project",
      projectId: "project-7",
      projectTab: "assets",
      assetId: null,
    });
  });

  it("parses an Engineering Asset segment nested under a known tab", () => {
    expect(parseAppRoute("/projects/project-7/assets/asset-9")).toEqual({
      view: "project",
      projectId: "project-7",
      projectTab: "assets",
      assetId: "asset-9",
    });
  });

  it("ignores an asset segment under an unknown tab", () => {
    expect(parseAppRoute("/projects/project-7/unknown/asset-9").assetId).toBeNull();
  });

  it("falls back to the overview for unknown project tabs", () => {
    expect(parseAppRoute("/projects/project-7/unknown").projectTab).toBe("overview");
  });

  it("recognizes the dedicated notification workspace", () => {
    expect(parseAppRoute("/notifications")).toEqual({
      view: "notifications",
      projectId: null,
      projectTab: "overview",
      assetId: null,
    });
  });
  it("recognizes plugin administration without leaking route details", () => {
    expect(parseAppRoute("/administration/plugins")).toEqual({
      view: "plugin-administration",
      projectId: null,
      projectTab: "overview",
      assetId: null,
    });
  });

  it("recognizes the account view", () => {
    expect(parseAppRoute("/account")).toEqual({
      view: "account",
      projectId: null,
      projectTab: "overview",
      assetId: null,
    });
  });
});

describe("projectAssetPath", () => {
  it("builds a path without an asset segment when no asset is selected", () => {
    expect(projectAssetPath("project-7", "assets", null)).toBe("/projects/project-7/assets");
  });

  it("builds a path with the asset segment when an asset is selected", () => {
    expect(projectAssetPath("project-7", "assets", "asset-9")).toBe(
      "/projects/project-7/assets/asset-9",
    );
  });
});
