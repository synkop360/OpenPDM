import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { expectNoPageOverflow, mockPrototypeApi, signInWithStoredSession } from "./prototype-fixtures";

async function tabTo(page: Page, control: Locator, label: string) {
  await expect(control, `${label} should be visible before keyboard navigation`).toBeVisible();

  for (let attempt = 0; attempt < 80; attempt += 1) {
    await page.keyboard.press("Tab");
    if (await control.evaluate((element) => element === document.activeElement)) {
      await expect(control).toBeFocused();
      return;
    }
  }

  await expect(control, `Expected Tab navigation to reach ${label}`).toBeFocused();
}

async function openNavigationPanelByKeyboardWhenCollapsed(page: Page) {
  const openNavigation = page.getByRole("button", { name: "Open navigation" });
  if (await openNavigation.isVisible()) {
    await tabTo(page, openNavigation, "Open navigation button");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Close navigation", exact: true })).toBeVisible();
  }
}

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
  await page.goto("/projects/project-1/overview");
  await expect(page.getByRole("heading", { name: /Prototype Project/i })).toBeVisible();

  await tabTo(page, page.getByRole("button", { name: "Collaboration", exact: true }), "Collaboration route button");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/projects\/project-1\/collaboration$/);
  await expect(page.getByRole("heading", { name: /Collaboration/i })).toBeVisible();

  await tabTo(page, page.getByRole("button", { name: "Members", exact: true }), "Members route button");
  await page.keyboard.press("Space");
  await expect(page).toHaveURL(/\/projects\/project-1\/members$/);
  await expect(page.getByRole("heading", { name: "Members", exact: true })).toBeVisible();

  await page.goto("/projects/project-1/overview");
  await openNavigationPanelByKeyboardWhenCollapsed(page);
  await tabTo(page, page.getByRole("button", { name: "Plugin administration", exact: true }), "Plugin administration route button");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/administration\/plugins$/);
  await expect(page.getByRole("heading", { name: /Plugin Administration/i })).toBeVisible();
});
