import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import {
  expectNoPageOverflow,
  mockFirstRunPrototypeApi,
  mockPrototypeApi,
  mockPrototypeMutations,
  signInWithStoredSession,
} from "./prototype-fixtures";

test("usable prototype supports generic Engineering Asset collaboration path", async ({ page }) => {
  await mockPrototypeApi(page);
  await mockPrototypeMutations(page);
  await signInWithStoredSession(page);

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

  const createdRevision = page.locator(".timeline-card").filter({
    has: page.getByRole("heading", { name: /^Revision 2$/i }),
  });
  await expect(createdRevision).toBeVisible();
  await expect(createdRevision.getByText("Prototype check-in")).toBeVisible();
  await expect(createdRevision.locator("strong", { hasText: "sample.txt" })).toBeVisible();
  await expect(createdRevision.getByText("text/plain")).toBeVisible();
  await expect(page.getByRole("heading", { name: "revision.created" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await createdRevision.getByRole("button", { name: /^Download$/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("sample.txt");
  const downloadedPath = await download.path();
  expect(downloadedPath).not.toBeNull();
  expect(await readFile(downloadedPath!, "utf-8")).toBe("hello world");
  await expectNoPageOverflow(page);
});

test("first-run user can create Organization, Project and Engineering Asset", async ({ page }) => {
  await mockFirstRunPrototypeApi(page);

  await page.goto("/");
  await page.getByRole("button", { name: /Register/i }).click();
  await page.getByLabel(/Display name/i).fill("Prototype Owner");
  await page.getByLabel(/Email/i).fill("prototype-owner@example.com");
  await page.getByLabel(/Password/i).fill("secret123");
  await page.getByRole("button", { name: /Create account/i }).click();
  await expect(page.getByText(/Create your first Organization/i)).toBeVisible();

  await page.getByLabel(/Organization name/i).fill("Prototype Org");
  await page.getByLabel(/Slug/i).fill("prototype-org");
  await page.getByRole("button", { name: /Create Organization/i }).evaluate((button) => {
    button.closest("form")?.requestSubmit();
  });
  await expect(page.getByText(/Create the first Project/i)).toBeVisible();

  await page.getByLabel(/Project name/i).fill("Prototype Project");
  await page.getByLabel(/Description/i).fill("Local prototype");
  await page.getByRole("button", { name: /Create Project/i }).evaluate((button) => {
    button.closest("form")?.requestSubmit();
  });
  await expect(page.getByRole("button", { name: "Prototype Project", exact: true })).toBeVisible();

  await page.goto("/projects/project-1/assets");
  await page.getByText(/Create Engineering Asset/i).click();
  await page.getByLabel(/Asset name/i).fill("Prototype Asset");
  await page.getByLabel(/Description/i).fill("Generic Engineering Asset");
  const createAssetRequest = page.waitForRequest((request) =>
    request.method() === "POST" && request.url().includes("/projects/project-1/assets"));
  await page.getByRole("button", { name: /Create Asset/i }).evaluate((button) => {
    button.closest("form")?.requestSubmit();
  });
  await createAssetRequest;
  await expect(page.getByText(/Engineering Asset created/i)).toBeVisible();
  await expectNoPageOverflow(page);
});
