import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import {
  createSharedPrototypeState,
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
  await page.getByRole("button", { name: /^History & Collaboration$/i }).click();

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

  await page.getByRole("button", { name: /^Metadata & Analysis$/i }).click();
  await expect(page.getByLabel("Representation to analyze")).toHaveValue("rep-1");
  await page.getByRole("button", { name: "Analyze representation" }).click();
  await expect(page.getByText("Analysis complete: 1 metadata, 0 references, 0 relationships.")).toBeVisible();
  await expect(page.getByText("plugin.analysis.status")).toBeVisible();
  await expect(page.getByRole("button", { name: /^(command|executable|launch)/i })).toHaveCount(0);

  await page.getByRole("button", { name: /^History & Collaboration$/i }).click();
  const downloadPromise = page.waitForEvent("download");
  await createdRevision.getByRole("button", { name: /^Download$/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("sample.txt");
  const downloadedPath = await download.path();
  expect(downloadedPath).not.toBeNull();
  expect(await readFile(downloadedPath!, "utf-8")).toBe("hello world");
  await expectNoPageOverflow(page);
});

test("a direct navigation to an Engineering Asset URL renders the SPA with that Asset selected", async ({ page }) => {
  await mockPrototypeApi(page);
  await mockPrototypeMutations(page);
  await signInWithStoredSession(page);

  await page.goto("/projects/project-1/assets/asset-1");
  await expect(page.getByRole("heading", { name: /Asset detail and Revision history/i })).toBeVisible();
  await page.getByRole("button", { name: /^History & Collaboration$/i }).click();
  await expect(page.getByRole("button", { name: /^Check out$/i })).toBeVisible();
  await expect(page).toHaveURL(/\/projects\/project-1\/assets\/asset-1$/);
  await expectNoPageOverflow(page);
});

test("two users see lock conflict and collaboration notifications", async ({ browser }) => {
  const sharedState = createSharedPrototypeState();
  const owner = await browser.newContext();
  const member = await browser.newContext();
  const ownerPage = await owner.newPage();
  const memberPage = await member.newPage();

  await mockPrototypeApi(ownerPage, { state: sharedState, user: "owner" });
  await mockPrototypeMutations(ownerPage, { user: "owner" });
  await signInWithStoredSession(ownerPage);
  await mockPrototypeApi(memberPage, { state: sharedState, user: "member" });
  await mockPrototypeMutations(memberPage, { user: "member" });
  await signInWithStoredSession(memberPage);

  await memberPage.goto("/projects/project-1/collaboration");
  await expect(memberPage.getByRole("heading", { name: /Collaboration/i })).toBeVisible();
  await expect(memberPage.getByText("available", { exact: true })).toBeVisible();

  await ownerPage.goto("/projects/project-1/assets");
  await expect(ownerPage.getByRole("heading", { name: /Asset detail and Revision history/i })).toBeVisible();
  await ownerPage.getByRole("button", { name: /^History & Collaboration$/i }).click();
  await ownerPage.getByRole("button", { name: /^Check out$/i }).click();
  await expect(ownerPage.getByText("locked", { exact: true })).toBeVisible();

  await memberPage.goto("/projects/project-1/assets");
  await expect(memberPage.getByRole("heading", { name: /Asset detail and Revision history/i })).toBeVisible();
  await memberPage.getByRole("button", { name: /^History & Collaboration$/i }).click();
  await expect(memberPage.getByText("locked", { exact: true })).toBeVisible();
  await expect(memberPage.getByRole("button", { name: /^Check out$/i })).toBeDisabled();

  await memberPage.goto("/notifications");
  await expect(memberPage.locator("article").filter({ hasText: "Asset locked" })).toBeVisible();
  await memberPage.getByRole("button", { name: /Mark read/i }).first().click();
  await expect(memberPage.getByText(/Notification marked as read/i)).toBeVisible();

  await expectNoPageOverflow(ownerPage);
  await expectNoPageOverflow(memberPage);
  await owner.close();
  await member.close();
});

test("Asset Graph separates incoming, outgoing and references without bulk controls", async ({ page }) => {
  await mockPrototypeApi(page);
  await signInWithStoredSession(page);

  await page.goto("/projects/project-1/relationships");
  await expect(page.getByRole("heading", { name: /Relationships and references/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Incoming$/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Outgoing$/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^References$/i })).toBeVisible();
  await expect(page.getByRole("region", { name: "Incoming" }).getByText(/Incoming Asset/i)).toBeVisible();
  await expect(page.getByRole("region", { name: "Outgoing" }).getByText(/Referenced Asset/i)).toBeVisible();
  await expect(page.getByText(/Supplier specification/i)).toBeVisible();
  await expect(page.getByText(/bounded nodes/i)).toBeVisible();
  await expect(page.getByText(/read-only by design/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /bulk/i })).toHaveCount(0);
  await expectNoPageOverflow(page);
});

test("Platform Administrator can demonstrate the generic plugin provider path", async ({ page }) => {
  await mockPrototypeApi(page);
  await signInWithStoredSession(page);

  await page.goto("/administration/plugins");
  await expect(page.getByRole("heading", { name: /Plugin administration/i })).toBeVisible();
  await expect(page.getByText(/Install Community Plugin/i)).toBeVisible();
  await expect(page.getByText(/Asset Categories/i).first()).toBeVisible();
  await expect(page.getByText(/metadata_provider/i)).toBeVisible();
  await page.getByText(/Review manifest and package evidence/i).click();
  await expect(page.getByText(/Extension API/i)).toBeVisible();

  await page.getByRole("button", { name: /^Disable$/i }).click();
  await page.getByRole("button", { name: /^Disable plugin$/i }).click();
  await expect(page.getByText(/Asset Categories disabled/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /^Enable$/i })).toBeVisible();

  await page.getByRole("button", { name: /^Enable$/i }).click();
  await page.getByRole("button", { name: /^Enable plugin$/i }).click();
  await expect(page.getByText(/Asset Categories enabled/i)).toBeVisible();

  await page.goto("/projects/project-1/assets");
  await expect(page.getByRole("heading", { name: /Asset detail and Revision history/i })).toBeVisible();
  await expect(page.getByText(/Asset Categories/i).first()).toBeVisible();
  await page.getByLabel(/Engineering Asset category/i).selectOption("assembly");
  await page.getByRole("button", { name: /Apply metadata/i }).click();
  await expect(page.getByText(/Asset Categories metadata applied/i)).toBeVisible();
  await expect(page.getByText("classification.category")).toBeVisible();
  await expect(page.locator(".metadata-list").getByText("assembly", { exact: true })).toBeVisible();

  await page.goto("/administration/plugins");
  await page.getByRole("button", { name: /^Disable$/i }).click();
  await page.getByRole("button", { name: /^Disable plugin$/i }).click();
  await expect(page.getByText(/Asset Categories disabled/i)).toBeVisible();
  await page.goto("/projects/project-1/assets");
  await expect(page.getByText(/No running Metadata Provider is available/i)).toBeVisible();
  await expect(page.getByText("classification.category")).toBeVisible();
  await expect(page.locator(".metadata-list").getByText("assembly", { exact: true })).toBeVisible();
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
