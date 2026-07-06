import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

type JsonResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

function jsonResponse(payload: unknown, status = 200): JsonResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
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

    expect(await screen.findByRole("heading", { name: /OpenPDM Web UI Prototype/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register" })).toBeInTheDocument();
  });

  it("loads the authenticated workspace and revision history from the public API", async () => {
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
        if (path === "/projects/project-1/assets") {
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
            state: "available",
            can_checkin: false,
            can_unlock: false,
            can_force_unlock: false,
            lock: null,
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
        if (path === "/notifications") {
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

    expect(await screen.findByText("Owner")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Acme/i })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Rocket/i })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Wing Panel/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Collaboration state" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Check out" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Collaboration notifications" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Asset relationships" })).toBeInTheDocument();
    expect(await screen.findByText("Supplier specification")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Bounded graph summary" })).toBeInTheDocument();
    expect(await screen.findByText("Asset locked")).toBeInTheDocument();
    expect(await screen.findByText("Revision 1")).toBeInTheDocument();
    expect(await screen.findByText("AssetCreated")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Download" })).toBeInTheDocument();
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
        if (path === "/projects/project-1/assets") {
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
        if (path === "/notifications") {
          return jsonResponse([]);
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    render(<App />);

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
        if (path === "/projects/project-1/assets") {
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
        if (path === "/notifications") {
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
      if (path === "/projects/project-1/assets") {
        return jsonResponse([]);
      }
      if (path === "/notifications") {
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
});
