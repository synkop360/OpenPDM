import { describe, expect, it } from "vitest";
import { API_PROXY_PATHS } from "./apiRoutes";

describe("Vite API proxy", () => {
  it("forwards provider discovery to the OpenPDM backend", async () => {
    expect(API_PROXY_PATHS).toContain("/providers");
    expect(API_PROXY_PATHS).toContain("/plugins");
  });
});
