import { render, screen } from "@testing-library/react";
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
    expect(await screen.findByText("Revision 1")).toBeInTheDocument();
    expect(await screen.findByText("AssetCreated")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Download" })).toBeInTheDocument();
  });
});
