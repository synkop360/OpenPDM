import { expect, type Page } from "@playwright/test";

export async function mockPrototypeApi(page: Page) {
  await page.route("**/foundation", (route) => route.fulfill({
    json: { name: "OpenPDM", version: "0.0.0", phase: "Core Platform", architecture: "Modular Monolith" },
  }));
  await page.route("**/auth/session", (route) => route.fulfill({
    json: { id: "session-1", token: "token", user: { id: "user-owner", email: "owner@example.com", display_name: "Owner", is_active: true, is_platform_admin: true, created_at: "2026-07-28T00:00:00Z" } },
  }));
  await page.route("**/organizations", (route) => route.fulfill({
    json: [{ id: "org-member-1", role: "Owner", user: { id: "user-owner", email: "owner@example.com", display_name: "Owner" }, organization: { id: "org-1", name: "Prototype Org", slug: "prototype-org" } }],
  }));
  await page.route("**/organizations/org-1/projects/me", (route) => route.fulfill({
    json: [{ id: "project-member-1", role: "Owner", user: { id: "user-owner", email: "owner@example.com", display_name: "Owner" }, project: { id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" } }],
  }));
  await page.route("**/organizations/org-1/projects", (route) => route.fulfill({
    json: [{ id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" }],
  }));
  await page.route("**/organizations/org-1/members", (route) => route.fulfill({
    json: [{ id: "org-member-1", role: "Owner", user: { id: "user-owner", email: "owner@example.com", display_name: "Owner" }, organization: { id: "org-1", name: "Prototype Org", slug: "prototype-org" } }],
  }));
  await page.route("**/projects/project-1/members", (route) => {
    if (route.request().resourceType() !== "fetch") return route.fallback();
    return route.fulfill({
      json: [{ id: "project-member-1", role: "Owner", user: { id: "user-owner", email: "owner@example.com", display_name: "Owner" }, project: { id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" } }],
    });
  });
  await page.route("**/projects/project-1/assets**", (route) => route.fulfill({
    json: { items: [{ id: "asset-1", project_id: "project-1", name: "Prototype Asset", description: "Generic Engineering Asset", status: "draft", metadata: {}, created_at: "2026-07-28T00:00:00Z" }], next_cursor: null },
  }));
  await page.route("**/assets/asset-1", (route) => route.fulfill({
    json: { id: "asset-1", project_id: "project-1", name: "Prototype Asset", description: "Generic Engineering Asset", status: "draft", metadata: {}, created_at: "2026-07-28T00:00:00Z" },
  }));
  await page.route("**/assets/asset-1/history", (route) => route.fulfill({
    json: [{ id: "rev-1", asset_id: "asset-1", revision_number: 1, comment: "Initial revision", representations: [], created_at: "2026-07-28T00:00:00Z" }],
  }));
  await page.route("**/assets/asset-1/collaboration-state", (route) => route.fulfill({
    json: { asset_id: "asset-1", state: "available", can_checkout: true, can_checkin: false, can_unlock: false, can_force_unlock: false, lock: null },
  }));
  await page.route("**/assets/asset-1/timeline", (route) => route.fulfill({ json: [] }));
  await page.route("**/notifications**", (route) => route.fulfill({ json: { items: [], next_cursor: null } }));
  await page.route("**/providers", (route) => route.fulfill({ json: [] }));
}

export async function signInWithStoredSession(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("openpdm.sessionToken", "token");
    window.localStorage.setItem("openpdm.organizationId", "org-1");
    window.localStorage.setItem("openpdm.projectId", "project-1");
    window.localStorage.setItem("openpdm.assetId", "asset-1");
  });
}

export async function expectNoPageOverflow(page: Page) {
  const dimensions = await page.evaluate(() => {
    const root = document.documentElement;
    const overflowing = Array.from(document.querySelectorAll<HTMLElement>("*")).filter(
      (element) => element.getBoundingClientRect().right > root.clientWidth,
    ).map((element) => {
      const rect = element.getBoundingClientRect();
      return {
        className: element.className,
        minWidth: window.getComputedStyle(element).minWidth,
        right: Math.round(rect.right),
        tagName: element.tagName,
        width: Math.round(rect.width),
      };
    }).slice(0, 10);
    return { clientWidth: root.clientWidth, overflowing, scrollWidth: root.scrollWidth };
  });
  expect(dimensions.scrollWidth, JSON.stringify(dimensions.overflowing)).toBeLessThanOrEqual(dimensions.clientWidth);
}
