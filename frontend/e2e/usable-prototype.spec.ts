import { expect, test } from "@playwright/test";
import {
  expectNoPageOverflow,
  mockPrototypeApi,
  mockPrototypeMutations,
  signInWithStoredSession,
} from "./prototype-fixtures";

test.beforeEach(async ({ page }) => {
  await mockPrototypeApi(page);
  await mockPrototypeMutations(page);
  await signInWithStoredSession(page);
});

test("usable prototype supports generic Engineering Asset collaboration path", async ({ page }) => {
  await page.goto("/projects/project-1/assets");
  await expect(page.getByRole("heading", { name: /Engineering Assets/i })).toBeVisible();
  const prototypeAsset = page.getByRole("button", { name: /Prototype Asset/i });
  await prototypeAsset.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: /Asset detail and Revision history/i })).toBeVisible();

  await page.getByRole("button", { name: /^Check out$/i }).click();
  await expect(page.getByText("locked", { exact: true })).toBeVisible();

  await page.getByLabel(/revision comment/i).fill("Prototype check-in");
  await page.getByLabel(/file/i).setInputFiles({
    name: "sample.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("hello world"),
  });
  await page.getByRole("button", { name: /check in revision/i }).click();
  await expect(page.getByText(/Check-in complete/i)).toBeVisible();
  await expectNoPageOverflow(page);
});
