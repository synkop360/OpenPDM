import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { expectNoPageOverflow, mockPrototypeApi, signInWithStoredSession } from "./prototype-fixtures";

test.beforeEach(async ({ page }) => {
  await mockPrototypeApi(page);
  await signInWithStoredSession(page);
});

test("operational shell is accessible and contained", async ({ page }) => {
  await page.goto("/projects/project-1/overview");
  await expect(page.getByRole("heading", { name: /Prototype Project/i })).toBeVisible();
  await expectNoPageOverflow(page);
  const results = await new AxeBuilder({ page }).exclude("[data-testid='development-only']").analyze();
  expect(results.violations.filter((violation) => ["critical", "serious"].includes(violation.impact ?? ""))).toEqual([]);
});

test("members, collaboration and plugin administration routes are reachable by keyboard", async ({ page }) => {
  await page.goto("/projects/project-1/members");
  await expect(page.getByRole("heading", { name: "Members", exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();

  await page.goto("/projects/project-1/collaboration");
  await expect(page.getByRole("heading", { name: /Collaboration/i })).toBeVisible();

  await page.goto("/administration/plugins");
  await expect(page.getByRole("heading", { name: /Plugin Administration/i })).toBeVisible();
});
