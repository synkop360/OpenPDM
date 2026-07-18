import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

type JsonResponse = {
  ok: boolean;
  status: number;
  headers: Headers;
  json: () => Promise<unknown>;
};

function jsonResponse(payload: unknown, status = 200): JsonResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => payload,
  };
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/");
    vi.restoreAllMocks();
  });

  it("shows the local authentication shell when no session is stored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/foundation") {
          return jsonResponse({
            name: "OpenPDM",
            version: "0.0.0",
            phase: "Core Platform",
            architecture: "Modular Monolith",
          });
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    render(<App />);

    expect(await screen.findByRole("heading", { name: "OpenPDM" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register" })).toBeInTheDocument();
  });

  it("loads the authenticated workspace and revision history from the public API", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");
    window.localStorage.setItem("openpdm.assetId", "asset-1");
    window.sessionStorage.setItem("openpdm.transfer.user-1.asset-1", JSON.stringify({
      userId: "user-1", assetId: "asset-1", sessionId: "session-1", blobId: "blob-recovered",
      fileName: "native.fcstd", fileSize: 1234, fileType: "application/octet-stream",
      fileLastModified: 42,
    }));
    window.sessionStorage.setItem("openpdm.transfer.user-2.asset-1", JSON.stringify({
      userId: "user-2", assetId: "asset-1", sessionId: "other-session", blobId: null,
      fileName: "other.step", fileSize: 5, fileType: "application/step", fileLastModified: 1,
    }));

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path === "/foundation") {
          return jsonResponse({
            name: "OpenPDM",
            version: "0.0.0",
            phase: "Core Platform",
            architecture: "Modular Monolith",
          });
        }
        if (path === "/auth/session") {
          return jsonResponse({
            id: "session-1",
            token: "token-123",
            user: {
              id: "user-1",
              email: "owner@example.com",
              display_name: "Owner",
              is_active: true,
              created_at: "2026-01-01T00:00:00",
            },
          });
        }
        if (path === "/organizations") {
          return jsonResponse([
            {
              id: "membership-1",
              role: "Owner",
              organization: {
                id: "org-1",
                name: "Acme",
                slug: "acme",
                created_at: "2026-01-01T00:00:00",
              },
            },
          ]);
        }
        if (path === "/organizations/org-1/projects/me") {
          return jsonResponse([
            {
              id: "project-membership-1",
              role: "Owner",
              project: {
                id: "project-1",
                organization_id: "org-1",
                name: "Rocket",
                description: "Launch vehicle",
                created_at: "2026-01-01T00:00:00",
              },
            },
          ]);
        }
        if (path === "/organizations/org-1/projects") {
          return jsonResponse([
            {
              id: "project-1",
              organization_id: "org-1",
              name: "Rocket",
              description: "Launch vehicle",
              created_at: "2026-01-01T00:00:00",
            },
          ]);
        }
        if ((path === "/projects/project-1/assets" || path.startsWith("/projects/project-1/assets/page?"))) {
          return jsonResponse([
            {
              id: "asset-1",
              project_id: "project-1",
              name: "Wing Panel",
              description: "Primary structure",
              status: "active",
              created_by_user_id: "user-1",
              created_at: "2026-01-01T00:00:00",
              updated_at: "2026-01-02T00:00:00",
              revisions: [],
            },
          ]);
        }
        if (path === "/assets/asset-1") {
          return jsonResponse({
            id: "asset-1",
            project_id: "project-1",
            name: "Wing Panel",
            description: "Primary structure",
            status: "active",
            created_by_user_id: "user-1",
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-02T00:00:00",
            revisions: [],
          });
        }
        if (path === "/assets/asset-1/history") {
          return jsonResponse([
            {
              id: "revision-1",
              asset_id: "asset-1",
              number: 1,
              comment: "Initial revision",
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:00:00",
              representations: [
                {
                  id: "representation-1",
                  revision_id: "revision-1",
                  name: "native.fcstd",
                  media_type: "application/octet-stream",
                  blob_id: "blob-1",
                  created_at: "2026-01-02T00:00:00",
                  blob: {
                    id: "blob-1",
                    storage_key: "blob-1",
                    filename: "native.fcstd",
                    media_type: "application/octet-stream",
                    size_bytes: 1234,
                    checksum_sha256: "abc",
                    created_at: "2026-01-02T00:00:00",
                  },
                },
              ],
            },
          ]);
        }
        if (path === "/assets/asset-1/relationships") {
          return jsonResponse([
            {
              id: "relationship-1",
              source_asset_id: "asset-1",
              target_asset_id: "asset-2",
              relationship_type: "depends_on",
              direction: "directed",
              metadata: { confidence: "high" },
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:30:00",
            },
          ]);
        }
        if (path === "/assets/asset-1/relationships/incoming") {
          return jsonResponse([
            {
              id: "relationship-2",
              source_asset_id: "asset-2",
              target_asset_id: "asset-1",
              relationship_type: "references",
              direction: "directed",
              metadata: {},
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:45:00",
            },
          ]);
        }
        if (path === "/assets/asset-1/relationships/outgoing") {
          return jsonResponse([
            {
              id: "relationship-1",
              source_asset_id: "asset-1",
              target_asset_id: "asset-2",
              relationship_type: "depends_on",
              direction: "directed",
              metadata: { confidence: "high" },
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:30:00",
            },
          ]);
        }
        if (path === "/assets/asset-1/references") {
          return jsonResponse([
            {
              id: "reference-1",
              source_asset_id: "asset-1",
              reference_type: "external_document",
              target_uri: "https://example.com/specifications/wing-panel",
              label: "Supplier specification",
              metadata: { source: "supplier" },
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:50:00",
            },
          ]);
        }
        if (path.startsWith("/assets/asset-1/graph")) {
          return jsonResponse({
            asset_id: "asset-1",
            direction: "both",
            max_depth: 3,
            target_asset_id: null,
            path_exists: null,
            has_cycle: false,
            nodes: [
              { id: "asset-1", project_id: "project-1", name: "Wing Panel", status: "active" },
              { id: "asset-2", project_id: "project-1", name: "Spar", status: "active" },
            ],
            relationships: [
              {
                id: "relationship-1",
                source_asset_id: "asset-1",
                target_asset_id: "asset-2",
                relationship_type: "depends_on",
                direction: "directed",
                metadata: {},
                created_by_user_id: "user-1",
                created_at: "2026-01-02T00:30:00",
              },
            ],
          });
        }
        if (path === "/assets/asset-1/collaboration-state") {
          return jsonResponse({
            asset_id: "asset-1",
            state: "locked",
            can_checkin: true,
            can_unlock: false,
            can_force_unlock: false,
            lock: { owner_user_id: "user-1" },
          });
        }
        if (path === "/assets/asset-1/timeline") {
          return jsonResponse([
            {
              event_type: "AssetCreated",
              occurred_at: "2026-01-01T00:00:00",
              actor_user_id: "user-1",
              asset_id: "asset-1",
              revision_id: null,
              details: {},
            },
          ]);
        }
        if (path === "/providers") {
          return jsonResponse([
            {
              id: "org.openpdm.examples.asset-categories",
              name: "Asset Categories API Test Plugin",
              capabilities: ["metadata_provider", "option_provider"],
            },
          ]);
        }
        if (path === "/plugins/org.openpdm.examples.asset-categories/providers/options") {
          return jsonResponse([
            {
              key: "category",
              label: "Asset category",
              options: [
                { value: "document", label: "Document" },
                { value: "drawing", label: "Drawing" },
              ],
            },
          ]);
        }
        if (path === "/metadata/asset/asset-1") {
          return jsonResponse([]);
        }
        if (path === "/blobs/upload-sessions/session-1") {
          return jsonResponse({
            id: "session-1", filename: "native.fcstd", media_type: "application/octet-stream",
            total_size_bytes: 1234, checksum_sha256: null, chunk_size_bytes: 512,
            status: "completed", received_bytes: 1234, received_chunk_numbers: [0, 1, 2],
            expires_at: "2026-07-19T00:00:00Z", created_at: "2026-07-18T00:00:00Z",
            updated_at: "2026-07-18T00:00:00Z",
            blob: { id: "blob-recovered", storage_key: "blob-recovered", filename: "native.fcstd",
              media_type: "application/octet-stream", size_bytes: 1234, checksum_sha256: "a".repeat(64),
              created_at: "2026-07-18T00:00:00Z" },
          });
        }
        if (path === "/assets/asset-1/checkin" && init?.method === "POST") {
          return jsonResponse({ id: "revision-2", asset_id: "asset-1", number: 2,
            comment: "Recovered transfer", created_by_user_id: "user-1",
            created_at: "2026-07-18T00:00:00Z", representations: [] }, 201);
        }
        if ((path === "/notifications" || path.startsWith("/notifications/page?"))) {
          return jsonResponse([
            {
              id: "notification-1",
              recipient_user_id: "user-1",
              actor_user_id: "user-2",
              organization_id: "org-1",
              project_id: "project-1",
              asset_id: "asset-1",
              revision_id: null,
              event_type: "asset.checked_out",
              is_read: false,
              read_at: null,
              details: { lock_owner_user_id: "user-2" },
              created_at: "2026-01-02T01:00:00",
            },
          ]);
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome, Owner" })).toBeInTheDocument();
    expect(await screen.findByText("Wing Panel")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Acme/i })).toBeInTheDocument();
    const projectButtons = await screen.findAllByRole("button", { name: /Rocket/i });
    fireEvent.click(projectButtons[0]);
    expect(window.location.pathname).toBe("/projects/project-1/overview");
    const projectWorkspace = await screen.findByRole("region", { name: "Rocket" });
    expect(projectWorkspace).toContainElement(screen.getByRole("heading", { name: "Recent Assets" }));
    expect(projectWorkspace).toContainElement(screen.getByRole("heading", { name: "Collaboration feed" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Assets" }));
    expect(window.location.pathname).toBe("/projects/project-1/assets");
    expect(await screen.findByRole("button", { name: /Wing Panel/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Collaboration state" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Check out" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Collaboration notifications" })).toBeInTheDocument();
    expect(await screen.findByText("Asset Categories API Test Plugin")).toBeInTheDocument();
    expect(await screen.findByLabelText("Asset category")).toBeInTheDocument();
    expect(screen.queryByText("No running Metadata Provider is available.")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Asset relationships" })).toBeInTheDocument();
    expect(await screen.findByText("Supplier specification")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Bounded graph summary" })).toBeInTheDocument();
    expect(await screen.findByText("Asset locked")).toBeInTheDocument();
    expect(await screen.findByText("Revision 1")).toBeInTheDocument();
    expect(await screen.findByText("AssetCreated")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Download" })).toBeInTheDocument();
    expect(await screen.findByText("Resume transfer")).toBeInTheDocument();
    const recoveredFile = new File([new Uint8Array(1234)], "native.fcstd", {
      type: "application/octet-stream", lastModified: 42,
    });
    fireEvent.change(screen.getByLabelText("Revision comment"), { target: { value: "Recovered transfer" } });
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [recoveredFile] } });
    fireEvent.submit(screen.getByRole("heading", { name: "Check in a new Revision" }).closest("form")!);
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) =>
      String(input) === "/assets/asset-1/checkin")).toBe(true));
    expect(await screen.findByText("Check-in complete")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("openpdm.transfer.user-1.asset-1")).toBeNull();
    expect(window.sessionStorage.getItem("openpdm.transfer.user-2.asset-1")).not.toBeNull();
    const calls = vi.mocked(fetch).mock.calls.map(([input, init]) => [String(input), init?.method ?? "GET"]);
    expect(calls).toContainEqual(["/blobs/upload-sessions/session-1", "GET"]);
    expect(calls.some(([path]) => path.includes("/chunks/"))).toBe(false);
  });

  it("navigates to a related asset through the relationship exploration surface", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");

    const assetsById = {
      "asset-1": {
        id: "asset-1",
        project_id: "project-1",
        name: "Wing Panel",
        description: "Primary structure",
        status: "active",
        created_by_user_id: "user-1",
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-02T00:00:00",
        revisions: [],
      },
      "asset-2": {
        id: "asset-2",
        project_id: "project-1",
        name: "Spar",
        description: "Load-bearing support",
        status: "active",
        created_by_user_id: "user-1",
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-03T00:00:00",
        revisions: [],
      },
    } as const;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/foundation") {
          return jsonResponse({
            name: "OpenPDM",
            version: "0.0.0",
            phase: "Core Platform",
            architecture: "Modular Monolith",
          });
        }
        if (path === "/auth/session") {
          return jsonResponse({
            id: "session-1",
            token: "token-123",
            user: {
              id: "user-1",
              email: "owner@example.com",
              display_name: "Owner",
              is_active: true,
              created_at: "2026-01-01T00:00:00",
            },
          });
        }
        if (path === "/organizations") {
          return jsonResponse([
            {
              id: "membership-1",
              role: "Owner",
              organization: {
                id: "org-1",
                name: "Acme",
                slug: "acme",
                created_at: "2026-01-01T00:00:00",
              },
            },
          ]);
        }
        if (path === "/organizations/org-1/projects/me") {
          return jsonResponse([
            {
              id: "project-membership-1",
              role: "Owner",
              project: {
                id: "project-1",
                organization_id: "org-1",
                name: "Rocket",
                description: "Launch vehicle",
                created_at: "2026-01-01T00:00:00",
              },
            },
          ]);
        }
        if (path === "/organizations/org-1/projects") {
          return jsonResponse([
            {
              id: "project-1",
              organization_id: "org-1",
              name: "Rocket",
              description: "Launch vehicle",
              created_at: "2026-01-01T00:00:00",
            },
          ]);
        }
        if ((path === "/projects/project-1/assets" || path.startsWith("/projects/project-1/assets/page?"))) {
          return jsonResponse([assetsById["asset-1"], assetsById["asset-2"]]);
        }
        if (path === "/assets/asset-1") {
          return jsonResponse(assetsById["asset-1"]);
        }
        if (path === "/assets/asset-2") {
          return jsonResponse(assetsById["asset-2"]);
        }
        if (path === "/assets/asset-1/history" || path === "/assets/asset-2/history") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/relationships") {
          return jsonResponse([
            {
              id: "relationship-1",
              source_asset_id: "asset-1",
              target_asset_id: "asset-2",
              relationship_type: "depends_on",
              direction: "directed",
              metadata: {},
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:30:00",
            },
          ]);
        }
        if (path === "/assets/asset-2/relationships") {
          return jsonResponse([
            {
              id: "relationship-1",
              source_asset_id: "asset-1",
              target_asset_id: "asset-2",
              relationship_type: "depends_on",
              direction: "directed",
              metadata: {},
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:30:00",
            },
          ]);
        }
        if (path === "/assets/asset-1/relationships/incoming") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-2/relationships/incoming") {
          return jsonResponse([
            {
              id: "relationship-1",
              source_asset_id: "asset-1",
              target_asset_id: "asset-2",
              relationship_type: "depends_on",
              direction: "directed",
              metadata: {},
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:30:00",
            },
          ]);
        }
        if (path === "/assets/asset-1/relationships/outgoing") {
          return jsonResponse([
            {
              id: "relationship-1",
              source_asset_id: "asset-1",
              target_asset_id: "asset-2",
              relationship_type: "depends_on",
              direction: "directed",
              metadata: {},
              created_by_user_id: "user-1",
              created_at: "2026-01-02T00:30:00",
            },
          ]);
        }
        if (path === "/assets/asset-2/relationships/outgoing") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/references" || path === "/assets/asset-2/references") {
          return jsonResponse([]);
        }
        if (path.startsWith("/assets/asset-1/graph")) {
          return jsonResponse({
            asset_id: "asset-1",
            direction: "both",
            max_depth: 3,
            target_asset_id: null,
            path_exists: null,
            has_cycle: false,
            nodes: [
              { id: "asset-1", project_id: "project-1", name: "Wing Panel", status: "active" },
              { id: "asset-2", project_id: "project-1", name: "Spar", status: "active" },
            ],
            relationships: [
              {
                id: "relationship-1",
                source_asset_id: "asset-1",
                target_asset_id: "asset-2",
                relationship_type: "depends_on",
                direction: "directed",
                metadata: {},
                created_by_user_id: "user-1",
                created_at: "2026-01-02T00:30:00",
              },
            ],
          });
        }
        if (path.startsWith("/assets/asset-2/graph")) {
          return jsonResponse({
            asset_id: "asset-2",
            direction: "both",
            max_depth: 3,
            target_asset_id: null,
            path_exists: null,
            has_cycle: false,
            nodes: [
              { id: "asset-1", project_id: "project-1", name: "Wing Panel", status: "active" },
              { id: "asset-2", project_id: "project-1", name: "Spar", status: "active" },
            ],
            relationships: [
              {
                id: "relationship-1",
                source_asset_id: "asset-1",
                target_asset_id: "asset-2",
                relationship_type: "depends_on",
                direction: "directed",
                metadata: {},
                created_by_user_id: "user-1",
                created_at: "2026-01-02T00:30:00",
              },
            ],
          });
        }
        if (path === "/assets/asset-1/collaboration-state" || path === "/assets/asset-2/collaboration-state") {
          return jsonResponse({
            asset_id: path.includes("asset-2") ? "asset-2" : "asset-1",
            state: "available",
            can_checkin: false,
            can_unlock: false,
            can_force_unlock: false,
            lock: null,
          });
        }
        if (path === "/assets/asset-1/timeline" || path === "/assets/asset-2/timeline") {
          return jsonResponse([]);
        }
        if ((path === "/notifications" || path.startsWith("/notifications/page?"))) {
          return jsonResponse([]);
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    render(<App />);

    const projectButtons = await screen.findAllByRole("button", { name: /Rocket/i });
    fireEvent.click(projectButtons[0]);
    fireEvent.click(await screen.findByRole("tab", { name: "Assets" }));
    expect(await screen.findByText("Wing Panel")).toBeInTheDocument();
    const openButtons = await screen.findAllByRole("button", { name: "Open asset" });
    fireEvent.click(openButtons[0]);
    expect(await screen.findByRole("heading", { name: "Asset relationships" })).toBeInTheDocument();
    expect(
      await screen.findByText(
        (_content, element) =>
          element?.tagName.toLowerCase() === "p" && element.textContent === "Load-bearing support",
      ),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Wing Panel/i })).toBeInTheDocument();
  });

  it("shows collaboration recovery guidance when checkout is rejected", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/foundation") {
          return jsonResponse({
            name: "OpenPDM",
            version: "0.0.0",
            phase: "Core Platform",
            architecture: "Modular Monolith",
          });
        }
        if (path === "/auth/session") {
          return jsonResponse({
            id: "session-1",
            token: "token-123",
            user: {
              id: "user-1",
              email: "owner@example.com",
              display_name: "Owner",
              is_active: true,
              created_at: "2026-01-01T00:00:00",
            },
          });
        }
        if (path === "/organizations") {
          return jsonResponse([
            {
              id: "membership-1",
              role: "Owner",
              organization: {
                id: "org-1",
                name: "Acme",
                slug: "acme",
                created_at: "2026-01-01T00:00:00",
              },
            },
          ]);
        }
        if (path === "/organizations/org-1/projects/me") {
          return jsonResponse([
            {
              id: "project-membership-1",
              role: "Owner",
              project: {
                id: "project-1",
                organization_id: "org-1",
                name: "Rocket",
                description: "Launch vehicle",
                created_at: "2026-01-01T00:00:00",
              },
            },
          ]);
        }
        if (path === "/organizations/org-1/projects") {
          return jsonResponse([
            {
              id: "project-1",
              organization_id: "org-1",
              name: "Rocket",
              description: "Launch vehicle",
              created_at: "2026-01-01T00:00:00",
            },
          ]);
        }
        if ((path === "/projects/project-1/assets" || path.startsWith("/projects/project-1/assets/page?"))) {
          return jsonResponse([
            {
              id: "asset-1",
              project_id: "project-1",
              name: "Wing Panel",
              description: "Primary structure",
              status: "active",
              created_by_user_id: "user-1",
              created_at: "2026-01-01T00:00:00",
              updated_at: "2026-01-02T00:00:00",
              revisions: [],
            },
          ]);
        }
        if (path === "/assets/asset-1") {
          return jsonResponse({
            id: "asset-1",
            project_id: "project-1",
            name: "Wing Panel",
            description: "Primary structure",
            status: "active",
            created_by_user_id: "user-1",
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-02T00:00:00",
            revisions: [],
          });
        }
        if (path === "/assets/asset-1/history") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/relationships") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/relationships/incoming") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/relationships/outgoing") {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/references") {
          return jsonResponse([]);
        }
        if (path.startsWith("/assets/asset-1/graph")) {
          return jsonResponse({
            asset_id: "asset-1",
            direction: "both",
            max_depth: 3,
            target_asset_id: null,
            path_exists: null,
            has_cycle: false,
            nodes: [{ id: "asset-1", project_id: "project-1", name: "Wing Panel", status: "active" }],
            relationships: [],
          });
        }
        if (path === "/assets/asset-1/collaboration-state") {
          return jsonResponse({
            asset_id: "asset-1",
            state: "available",
            can_checkin: false,
            can_unlock: false,
            can_force_unlock: false,
            lock: null,
          });
        }
        if (path === "/assets/asset-1/timeline") {
          return jsonResponse([]);
        }
        if ((path === "/notifications" || path.startsWith("/notifications/page?"))) {
          return jsonResponse([]);
        }
        if (path === "/assets/asset-1/checkout") {
          return jsonResponse(
            {
              detail: {
                code: "asset_locked",
                message: "Asset is already locked by another user.",
                context: {
                  request_id: "req-recovery-1",
                  recovery_action: "wait_or_coordinate",
                  should_refresh: true,
                  user_guidance:
                    "Wait for the current lock owner to release the Asset or ask a Maintainer or Owner to coordinate.",
                },
              },
            },
            409,
          );
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    render(<App />);

    const projectButtons = await screen.findAllByRole("button", { name: /Rocket/i });
    fireEvent.click(projectButtons[0]);
    fireEvent.click(await screen.findByRole("tab", { name: "Assets" }));
    const checkoutButton = await screen.findByRole("button", { name: "Check out" });
    fireEvent.click(checkoutButton);

    expect(await screen.findByRole("heading", { name: "Recovery guidance" })).toBeInTheDocument();
    expect(await screen.findByText(/Request ID: req-recovery-1/i)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Refresh asset state" })).toBeInTheDocument();
  });

  it("shows notifications and marks them as read through the public API", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/foundation") {
        return jsonResponse({
          name: "OpenPDM",
          version: "0.0.0",
          phase: "Core Platform",
          architecture: "Modular Monolith",
        });
      }
      if (path === "/auth/session") {
        return jsonResponse({
          id: "session-1",
          token: "token-123",
          user: {
            id: "user-1",
            email: "owner@example.com",
            display_name: "Owner",
            is_active: true,
            created_at: "2026-01-01T00:00:00",
          },
        });
      }
      if (path === "/organizations") {
        return jsonResponse([
          {
            id: "membership-1",
            role: "Owner",
            organization: {
              id: "org-1",
              name: "Acme",
              slug: "acme",
              created_at: "2026-01-01T00:00:00",
            },
          },
        ]);
      }
      if (path === "/organizations/org-1/projects/me") {
        return jsonResponse([
          {
            id: "project-membership-1",
            role: "Owner",
            project: {
              id: "project-1",
              organization_id: "org-1",
              name: "Rocket",
              description: "Launch vehicle",
              created_at: "2026-01-01T00:00:00",
            },
          },
        ]);
      }
      if (path === "/organizations/org-1/projects") {
        return jsonResponse([
          {
            id: "project-1",
            organization_id: "org-1",
            name: "Rocket",
            description: "Launch vehicle",
            created_at: "2026-01-01T00:00:00",
          },
        ]);
      }
      if ((path === "/projects/project-1/assets" || path.startsWith("/projects/project-1/assets/page?"))) {
        return jsonResponse([]);
      }
      if ((path === "/notifications" || path.startsWith("/notifications/page?"))) {
        return jsonResponse([
          {
            id: "notification-1",
            recipient_user_id: "user-1",
            actor_user_id: "user-2",
            organization_id: "org-1",
            project_id: "project-1",
            asset_id: "asset-1",
            revision_id: null,
            event_type: "collaboration.conflict_detected",
            is_read: false,
            read_at: null,
            details: {
              user_guidance: "Wait for the current lock owner to release the Asset.",
            },
            created_at: "2026-01-02T01:00:00",
          },
        ]);
      }
      if (path === "/notifications/notification-1/read") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          id: "notification-1",
          recipient_user_id: "user-1",
          actor_user_id: "user-2",
          organization_id: "org-1",
          project_id: "project-1",
          asset_id: "asset-1",
          revision_id: null,
          event_type: "collaboration.conflict_detected",
          is_read: true,
          read_at: "2026-01-02T02:00:00",
          details: {
            user_guidance: "Wait for the current lock owner to release the Asset.",
          },
          created_at: "2026-01-02T01:00:00",
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("Conflict detected")).toBeInTheDocument();
    const readButton = await screen.findByRole("button", { name: "Mark as read" });
    fireEvent.click(readButton);
    expect(await screen.findByText("read")).toBeInTheDocument();
  });

  it("lets an Owner add, change, and remove Organization and Project members", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const owner = { id: "user-1", email: "owner@example.com", display_name: "Owner", is_active: true, created_at: "2026-01-01T00:00:00" };
    const member = { id: "user-2", email: "member@example.com", display_name: "Member", is_active: true, created_at: "2026-01-01T00:00:00" };
    let organizationMembers = [{ id: "org-member-1", role: "Owner", user: owner }];
    let projectMembers = [{ id: "project-member-1", role: "Owner", user: owner }];

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path === "/foundation") return jsonResponse({ name: "OpenPDM", version: "0", phase: "Core Platform", architecture: "Modular Monolith" });
      if (path === "/auth/session") return jsonResponse({ id: "session-1", token: "token-123", user: owner });
      if (path === "/organizations") return jsonResponse([{ id: "org-member-1", role: "Owner", organization: { id: "org-1", name: "Acme", slug: "acme", created_at: "2026-01-01T00:00:00" } }]);
      if (path === "/organizations/org-1/projects/me") return jsonResponse([{ id: "project-member-1", role: "Owner", project: { id: "project-1", organization_id: "org-1", name: "Rocket", description: "", created_at: "2026-01-01T00:00:00" } }]);
      if (path === "/organizations/org-1/projects") return jsonResponse([{ id: "project-1", organization_id: "org-1", name: "Rocket", description: "", created_at: "2026-01-01T00:00:00" }]);
      if (path === "/organizations/org-1/members" && method === "GET") return jsonResponse(organizationMembers);
      if (path === "/organizations/org-1/members" && method === "POST") {
        organizationMembers = [...organizationMembers, { id: "org-member-2", role: "Viewer", user: member }];
        return jsonResponse(organizationMembers[1]);
      }
      if (path === "/projects/project-1/members" && method === "GET") return jsonResponse(projectMembers);
      if (path === "/projects/project-1/members" && method === "POST") {
        projectMembers = [...projectMembers, { id: "project-member-2", role: "Viewer", user: member }];
        return jsonResponse(projectMembers[1]);
      }
      if (path === "/projects/project-1/members/project-member-2" && method === "PATCH") {
        projectMembers = projectMembers.map((item) => item.id === "project-member-2" ? { ...item, role: "Contributor" } : item);
        return jsonResponse(projectMembers[1]);
      }
      if (path === "/projects/project-1/members/project-member-2" && method === "DELETE") {
        projectMembers = projectMembers.filter((item) => item.id !== "project-member-2");
        return jsonResponse(undefined, 204);
      }
      if ((path === "/projects/project-1/assets" || path.startsWith("/projects/project-1/assets/page?")) || (path === "/notifications" || path.startsWith("/notifications/page?"))) return jsonResponse([]);
      throw new Error(`Unexpected request: ${method} ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    const projectButtons = await screen.findAllByRole("button", { name: /Rocket/i });
    fireEvent.click(projectButtons[0]);
    fireEvent.click(await screen.findByRole("tab", { name: "Members" }));
    expect(await screen.findByRole("heading", { name: "Organization members" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "member@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Add member" }));
    expect(await screen.findAllByText("Member")).not.toHaveLength(0);

    fireEvent.change(screen.getByLabelText("User"), { target: { value: "user-2" } });
    fireEvent.click(screen.getByRole("button", { name: "Add to Project" }));
    const roleSelect = await screen.findByLabelText("Project role for Member");
    fireEvent.change(roleSelect, { target: { value: "Contributor" } });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/projects/project-1/members/project-member-2",
      expect.objectContaining({ method: "PATCH" }),
    ));
    const memberRow = (await screen.findByLabelText("Project role for Member")).closest(".member-row");
    const removeButton = memberRow?.querySelector("button");
    expect(removeButton).not.toBeNull();
    fireEvent.click(removeButton!);
    await waitFor(() => expect(screen.queryByLabelText("Project role for Member")).not.toBeInTheDocument());

    expect(screen.getByLabelText("Organization role for Owner")).toBeDisabled();
    expect(screen.getAllByText(/Final Owner/)).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "/organizations/org-1/members",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ user_email: "member@example.com", role: "Viewer" }) }),
    );
  });

  it("opens plugin administration for a Platform Administrator", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path === "/foundation") {
        return jsonResponse({
          name: "OpenPDM",
          version: "0.0.0",
          phase: "Engineering Platform",
          architecture: "Modular Monolith",
        });
      }
      if (path === "/auth/session") {
        return jsonResponse({
          id: "session-1",
          token: "token-123",
          user: {
            id: "user-1",
            email: "admin@example.com",
            display_name: "Admin",
            is_active: true,
            is_platform_admin: true,
            created_at: "2026-01-01T00:00:00",
          },
        });
      }
      if (path === "/organizations" || (path === "/notifications" || path.startsWith("/notifications/page?"))) return jsonResponse([]);
      if (path === "/plugins" && method === "GET") {
        return jsonResponse([
          {
            id: "org.example.categories",
            name: "Categories",
            version: "1.0.0",
            plugin_type: "community",
            capabilities: ["metadata_provider"],
            extension_api_versions: [1],
            lifecycle_state: "disabled",
            diagnostic_reason: null,
            enabled: false,
            package_digest: "a".repeat(64),
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-01T00:00:00",
          },
        ]);
      }
      if (path === "/plugins/org.example.categories/configuration" && method === "GET") {
        return jsonResponse({
          plugin_id: "org.example.categories",
          configuration_schema: { type: "object", properties: { prefix: { type: "string" }, token: { type: "string", secret: true } }, required: ["prefix", "token"], additionalProperties: false },
          values: { prefix: "current" },
          configured_secret_fields: ["token"],
          updated_at: "2026-01-01T00:00:00",
        });
      }
      if (path === "/plugins/org.example.categories/configuration" && method === "PUT") {
        return jsonResponse({
          plugin_id: "org.example.categories",
          configuration_schema: { type: "object", properties: { prefix: { type: "string" }, token: { type: "string", secret: true } }, required: ["prefix", "token"], additionalProperties: false },
          values: { prefix: "updated" },
          configured_secret_fields: ["token"],
          updated_at: "2026-01-02T00:00:00",
        });
      }
      if (path === "/plugins/org.example.categories/state" && method === "POST") {
        return jsonResponse({
          id: "org.example.categories",
          name: "Categories",
          version: "1.0.0",
          plugin_type: "community",
          capabilities: ["metadata_provider"],
          extension_api_versions: [1],
          lifecycle_state: "running",
          diagnostic_reason: null,
          enabled: true,
          package_digest: "a".repeat(64),
          created_at: "2026-01-01T00:00:00",
          updated_at: "2026-01-01T00:00:00",
        });
      }
      throw new Error(`Unexpected request: ${method} ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Plugin administration" }));
    expect(window.location.pathname).toBe("/administration/plugins");
    expect(await screen.findByRole("heading", { name: "Plugin administration" })).toBeInTheDocument();
    expect(await screen.findByText("Categories")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Enable" }));
    fireEvent.click(await screen.findByRole("button", { name: "Enable plugin" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/plugins/org.example.categories/state",
        expect.objectContaining({ method: "POST" }),
      ),
    );    fireEvent.click(screen.getByRole("button", { name: "Configure" }));
    const secretInput = await screen.findByPlaceholderText("Secret configured — enter to replace");
    expect(secretInput).toHaveValue("");
    fireEvent.change(screen.getByLabelText("prefix (required)"), { target: { value: "updated" } });
    fireEvent.change(secretInput, { target: { value: "replacement-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/plugins/org.example.categories/configuration",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ values: { prefix: "updated", token: "replacement-secret" } }),
      }),
    ));
  });

  it("denies plugin administration to an ordinary authenticated user", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");
    window.history.replaceState({}, "", "/administration/plugins");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/foundation") {
          return jsonResponse({ name: "OpenPDM", version: "0.0.0", phase: "Engineering Platform", architecture: "Modular Monolith" });
        }
        if (path === "/auth/session") {
          return jsonResponse({
            id: "session-1",
            token: "token-123",
            user: {
              id: "user-2",
              email: "member@example.com",
              display_name: "Member",
              is_active: true,
              is_platform_admin: false,
              created_at: "2026-01-01T00:00:00",
            },
          });
        }
        if (path === "/organizations" || (path === "/notifications" || path.startsWith("/notifications/page?"))) return jsonResponse([]);
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Platform Administrator authority required" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Install package" })).not.toBeInTheDocument();
  });

  it("filters and acknowledges selected notifications in the dedicated queue", async () => {
    window.localStorage.setItem("openpdm.sessionToken", "token-123");

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method ?? "GET";
      if (path === "/foundation") {
        return jsonResponse({ name: "OpenPDM", version: "0.0.0", phase: "Core Platform", architecture: "Modular Monolith" });
      }
      if (path === "/auth/session") {
        return jsonResponse({
          id: "session-1",
          token: "token-123",
          user: {
            id: "user-1",
            email: "owner@example.com",
            display_name: "Owner",
            is_active: true,
            is_platform_admin: false,
            created_at: "2026-01-01T00:00:00",
          },
        });
      }
      if (path === "/organizations") return jsonResponse([]);
      if (path.startsWith("/notifications/page?") && method === "GET") {
        return jsonResponse({
          items: [{
            id: "notification-1",
            recipient_user_id: "user-1",
            actor_user_id: "user-2",
            organization_id: null,
            project_id: null,
            asset_id: null,
            revision_id: null,
            event_type: "asset.checked_out",
            is_read: false,
            read_at: null,
            details: {},
            created_at: "2026-01-02T01:00:00",
          }],
          next_cursor: null,
        });
      }
      if (path === "/notifications/read" && method === "POST") {
        return jsonResponse({ updated_count: 1, notification_ids: ["notification-1"] });
      }
      if (path === "/providers") return jsonResponse([]);
      throw new Error(`Unexpected request: ${method} ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByRole("heading", { name: "Welcome, Owner" });
    fireEvent.click(screen.getByLabelText("Notifications"));

    expect(window.location.pathname).toBe("/notifications");
    expect(await screen.findByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Select page" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark selected read" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/notifications/read",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ notification_ids: ["notification-1"] }),
      }),
    ));
    expect(await screen.findByText("1 notification marked as read.")).toBeInTheDocument();
  });});
