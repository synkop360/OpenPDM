import { expect, test } from "@playwright/test";
import {
  mockPrototypeApi,
  mockPrototypeMutations,
  signInWithStoredSession,
} from "./prototype-fixtures";

// Phase S: a browser-only user promotes a plugin-extracted analysis Reference into a
// generic depends_on Asset Graph edge by re-running the mapped contribution through the
// public analysis-provider endpoint. No API-only step.
test("maps an analysis-derived reference into a depends_on relationship from the Web UI", async ({ page }) => {
  await mockPrototypeApi(page);
  await mockPrototypeMutations(page);

  let mappedRelationship: Record<string, unknown> | null = null;

  const baseRelationship = {
    id: "rel-1",
    source_asset_id: "asset-1",
    target_asset_id: "asset-2",
    relationship_type: "depends_on",
    direction: "outgoing",
    metadata: { note: "Prototype dependency" },
    created_by_user_id: "user-owner",
    created_at: "2026-07-28T00:06:00Z",
  };

  // A revision that already carries a Blob-backed Representation so analysis is available.
  await page.route("**/assets/asset-1/history", (route) => route.fulfill({
    json: [
      {
        id: "rev-1",
        asset_id: "asset-1",
        number: 1,
        comment: "Initial revision",
        created_by_user_id: "user-owner",
        created_at: "2026-07-28T00:00:00Z",
        representations: [
          {
            id: "rep-1",
            revision_id: "rev-1",
            name: "SampleHarness.spliceproject",
            media_type: "application/json",
            blob_id: "blob-1",
            created_at: "2026-07-28T00:04:00Z",
            blob: {
              id: "blob-1",
              filename: "SampleHarness.spliceproject",
              media_type: "application/json",
              size_bytes: 2048,
              checksum_sha256: "a".repeat(64),
              created_at: "2026-07-28T00:04:00Z",
            },
          },
        ],
      },
    ],
  }));

  // An analysis-derived Reference carrying provider provenance (the shape the backend persists).
  await page.route("**/assets/asset-1/references", (route) => route.fulfill({
    json: [
      {
        id: "ref-analysis-1",
        source_asset_id: "asset-1",
        reference_type: "splicecad.bom_entry",
        target_uri: "splicecad://project/abc/bom/bom-1",
        label: "Generic connector 01",
        metadata: {
          "splicecad.bom_entry_id": "bom-1",
          analysis_provider_id: "asset-categories",
          analysis_contribution_key: "bom.bom-1",
        },
        created_by_user_id: "user-owner",
        created_at: "2026-07-28T00:08:00Z",
      },
    ],
  }));

  await page.route("**/assets/asset-1/relationships", (route) => route.fulfill({
    json: mappedRelationship ? [baseRelationship, mappedRelationship] : [baseRelationship],
  }));
  await page.route("**/assets/asset-1/relationships/outgoing", (route) => route.fulfill({
    json: mappedRelationship ? [baseRelationship, mappedRelationship] : [baseRelationship],
  }));

  await page.route("**/plugins/asset-categories/providers/analysis", (route) => {
    const body = route.request().postDataJSON() as { relationship_mappings?: Record<string, string> };
    const mappings = body?.relationship_mappings ?? {};
    if (mappings["bom.bom-1"]) {
      mappedRelationship = {
        id: "rel-analysis-1",
        source_asset_id: "asset-1",
        target_asset_id: mappings["bom.bom-1"],
        relationship_type: "depends_on",
        direction: "outgoing",
        metadata: {
          "splicecad.bom_entry_id": "bom-1",
          analysis_provider_id: "asset-categories",
          analysis_contribution_key: "bom.bom-1",
        },
        created_by_user_id: "user-owner",
        created_at: "2026-07-28T00:12:00Z",
      };
      return route.fulfill({
        json: { metadata: [], references: [], relationships: [mappedRelationship] },
      });
    }
    return route.fulfill({ json: { metadata: [], references: [], relationships: [] } });
  });

  await signInWithStoredSession(page);
  await page.goto("/projects/project-1/assets/asset-1");
  const metadataTab = page.getByRole("button", { name: "Metadata & Analysis" });
  await expect(metadataTab).toBeVisible();
  await metadataTab.click();

  const mappingCard = page.locator("article", {
    has: page.getByRole("heading", { name: "Map analysis dependencies" }),
  });
  await expect(mappingCard).toBeVisible();
  await expect(mappingCard.locator("code", { hasText: "bom.bom-1" })).toBeVisible();

  await mappingCard.getByLabel("Target Asset for bom.bom-1").selectOption({ label: "Referenced Asset" });
  await mappingCard.getByRole("button", { name: "Map as dependency" }).click();

  await expect(page.getByText("Dependency mapped from the analysis contribution.")).toBeVisible();
  await expect(mappingCard.getByText("Mapped as dependency on Referenced Asset.")).toBeVisible();
  await expect(mappingCard.getByRole("button", { name: "Map as dependency" })).toHaveCount(0);
});
