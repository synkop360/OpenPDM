import { describe, expect, it } from "vitest";
import { parseAppRoute } from "./routes";

describe("parseAppRoute", () => {
  it("parses project routes and known tabs", () => {
    expect(parseAppRoute("/projects/project-7/assets")).toEqual({
      view: "project",
      projectId: "project-7",
      projectTab: "assets",
    });
  });

  it("falls back to the overview for unknown project tabs", () => {
    expect(parseAppRoute("/projects/project-7/unknown").projectTab).toBe("overview");
  });

  it("recognizes plugin administration without leaking route details", () => {
    expect(parseAppRoute("/administration/plugins")).toEqual({
      view: "plugin-administration",
      projectId: null,
      projectTab: "overview",
    });
  });
});
