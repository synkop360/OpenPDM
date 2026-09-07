import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createLoadable } from "../../app/loadable";
import type { Asset, ProviderDescriptor, ReferenceRecord, Relationship } from "../../api";
import { MetadataAnalysisSection, type MetadataAnalysisSectionProps } from "./MetadataAnalysisSection";

const analysisProvider: ProviderDescriptor = {
  id: "org.openpdm.splice-cad",
  name: "Splice CAD Analysis",
  capabilities: ["analysis_provider"],
};

const analysisReference: ReferenceRecord = {
  id: "reference-bom-1",
  source_asset_id: "asset-1",
  reference_type: "splicecad.bom_entry",
  target_uri: "splicecad://project/abc/bom/bom-1",
  label: "Generic connector 01",
  metadata: {
    "splicecad.bom_entry_id": "bom-1",
    analysis_provider_id: "org.openpdm.splice-cad",
    analysis_contribution_key: "bom.bom-1",
  },
  created_by_user_id: "user-1",
  created_at: "2026-01-02T00:00:00",
};

const plainReference: ReferenceRecord = {
  id: "reference-plain-1",
  source_asset_id: "asset-1",
  reference_type: "external_document",
  target_uri: "https://example.com/spec",
  label: "Supplier specification",
  metadata: { source: "supplier" },
  created_by_user_id: "user-1",
  created_at: "2026-01-02T00:00:00",
};

const targetAsset: Asset = {
  id: "asset-2",
  project_id: "project-1",
  name: "ECU Harness",
  description: "",
  status: "active",
  created_by_user_id: "user-1",
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-01T00:00:00",
  revisions: [],
};

function baseProps(overrides: Partial<MetadataAnalysisSectionProps> = {}): MetadataAnalysisSectionProps {
  return {
    analysisBusy: false,
    analysisRepresentations: [
      {
        representation: {
          id: "representation-1",
          revision_id: "revision-1",
          name: "SampleHarness.spliceproject",
          media_type: "application/json",
          blob_id: "blob-1",
          created_at: "2026-01-01T00:00:00",
          blob: null,
        },
        revision: {
          id: "revision-1",
          asset_id: "asset-1",
          number: 1,
          comment: "initial",
          created_by_user_id: "user-1",
          created_at: "2026-01-01T00:00:00",
          representations: [],
        },
      },
    ],
    analysisResult: null,
    assetMetadata: createLoadable([]),
    assetReferences: createLoadable<ReferenceRecord[]>([analysisReference, plainReference]),
    assetRelationships: createLoadable<Relationship[]>([]),
    assetNameById: new Map([
      ["asset-1", "Wiring Harness"],
      ["asset-2", "ECU Harness"],
    ]),
    assets: [
      {
        id: "asset-1",
        project_id: "project-1",
        name: "Wiring Harness",
        description: "",
        status: "active",
        created_by_user_id: "user-1",
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
        revisions: [],
      },
      targetAsset,
    ],
    busyAction: null,
    onAnalysisRepresentationChange: vi.fn(),
    onApplyMetadataProvider: vi.fn(),
    onInvokeAnalysisProvider: vi.fn(),
    onMapAnalysisReference: vi.fn(),
    onProviderSelectionChange: vi.fn(),
    providerOptions: {},
    providers: { status: "ready", data: [analysisProvider], error: null },
    providerSelections: {},
    selectedAnalysisRepresentation: {
      id: "representation-1",
      revision_id: "revision-1",
      name: "SampleHarness.spliceproject",
      media_type: "application/json",
      blob_id: "blob-1",
      created_at: "2026-01-01T00:00:00",
      blob: null,
    },
    selectedAssetId: "asset-1",
    ...overrides,
  };
}

describe("MetadataAnalysisSection dependency mapping", () => {
  it("hides the mapping card when no reference carries analysis provenance", () => {
    render(<MetadataAnalysisSection {...baseProps({ assetReferences: createLoadable([plainReference]) })} />);
    expect(screen.queryByRole("heading", { name: "Map analysis dependencies" })).not.toBeInTheDocument();
  });

  it("lists only analysis-derived references and maps one through the provider", () => {
    const onMapAnalysisReference = vi.fn();
    render(<MetadataAnalysisSection {...baseProps({ onMapAnalysisReference })} />);

    const mappingCard = screen
      .getByRole("heading", { name: "Map analysis dependencies" })
      .closest("article") as HTMLElement;
    // exactly one mappable contribution: the plain supplier reference is excluded
    expect(within(mappingCard).getByText("bom.bom-1")).toBeInTheDocument();
    expect(within(mappingCard).queryByText("Supplier specification")).not.toBeInTheDocument();
    expect(within(mappingCard).getAllByRole("combobox")).toHaveLength(1);

    fireEvent.change(screen.getByLabelText("Target Asset for bom.bom-1"), {
      target: { value: "asset-2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Map as dependency" }));

    expect(onMapAnalysisReference).toHaveBeenCalledWith({
      providerId: "org.openpdm.splice-cad",
      contributionKey: "bom.bom-1",
      targetAssetId: "asset-2",
    });
  });

  it("shows a mapped contribution as resolved without a mapping control", () => {
    const mappedRelationship: Relationship = {
      id: "relationship-1",
      source_asset_id: "asset-1",
      target_asset_id: "asset-2",
      relationship_type: "depends_on",
      direction: "directed",
      metadata: {
        analysis_provider_id: "org.openpdm.splice-cad",
        analysis_contribution_key: "bom.bom-1",
      },
      created_by_user_id: "user-1",
      created_at: "2026-01-02T00:10:00",
    };
    render(
      <MetadataAnalysisSection
        {...baseProps({ assetRelationships: createLoadable([mappedRelationship]) })}
      />,
    );
    expect(screen.getByText("Mapped as dependency on ECU Harness.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Map as dependency" })).not.toBeInTheDocument();
  });

  it("blocks mapping until a Representation is selected", () => {
    render(
      <MetadataAnalysisSection {...baseProps({ selectedAnalysisRepresentation: null })} />,
    );
    expect(
      screen.getByText("Select a Representation to analyze above before mapping its contributions."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Map as dependency" })).toBeDisabled();
  });
});
