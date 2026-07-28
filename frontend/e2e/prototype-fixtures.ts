import { expect, type Page } from "@playwright/test";

type PrototypeBlob = {
  id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  created_at: string;
};

type PrototypeRevision = {
  id: string;
  asset_id: string;
  number: number;
  comment: string;
  created_by_user_id: string;
  created_at: string;
  representations: Array<{
    id: string;
    revision_id: string;
    name: string;
    media_type: string;
    blob_id: string | null;
    created_at: string;
    blob: PrototypeBlob | null;
  }>;
};

type PrototypeState = {
  collaborationState: {
    asset_id: string;
    state: "available" | "locked";
    can_checkout: boolean;
    can_checkin: boolean;
    can_unlock: boolean;
    can_force_unlock: boolean;
    lock: { id: string; asset_id: string; owner_user_id: string; created_at: string } | null;
  };
  history: PrototypeRevision[];
  timeline: Array<{
    event_type: string;
    occurred_at: string;
    actor_user_id: string | null;
    asset_id: string;
    revision_id: string | null;
    details: Record<string, unknown>;
  }>;
  notifications: Record<string, Array<{
    id: string;
    recipient_user_id: string;
    actor_user_id: string | null;
    organization_id: string | null;
    project_id: string;
    asset_id: string | null;
    revision_id: string | null;
    event_type: string;
    is_read: boolean;
    read_at: string | null;
    details: Record<string, unknown>;
    created_at: string;
  }>>;
  pluginEnabled: boolean;
  metadata: Array<{
    id: string;
    asset_id: string | null;
    revision_id: string | null;
    representation_id: string | null;
    key: string;
    value: unknown;
    value_type: string;
    source: string;
    created_at: string;
  }>;
};

const revisionBlob: PrototypeBlob = {
  id: "blob-1",
  filename: "sample.txt",
  media_type: "text/plain",
  size_bytes: 11,
  checksum_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  created_at: "2026-07-28T00:04:00Z",
};

const initialRevision: PrototypeRevision = {
  id: "rev-1",
  asset_id: "asset-1",
  number: 1,
  comment: "Initial revision",
  created_by_user_id: "user-owner",
  created_at: "2026-07-28T00:00:00Z",
  representations: [],
};

const checkedInRevision: PrototypeRevision = {
  id: "rev-2",
  asset_id: "asset-1",
  number: 2,
  comment: "Prototype check-in",
  created_by_user_id: "user-owner",
  created_at: "2026-07-28T00:05:00Z",
  representations: [{
    id: "rep-1",
    revision_id: "rev-2",
    name: "sample.txt",
    media_type: "text/plain",
    blob_id: "blob-1",
    created_at: "2026-07-28T00:05:00Z",
    blob: revisionBlob,
  }],
};

const prototypeStates = new WeakMap<Page, PrototypeState>();

const ownerUser = {
  id: "user-owner",
  email: "owner@example.com",
  display_name: "Owner",
  is_active: true,
  is_platform_admin: true,
  created_at: "2026-07-28T00:00:00Z",
};

const memberUser = {
  id: "user-member",
  email: "member@example.com",
  display_name: "Member",
  is_active: true,
  is_platform_admin: false,
  created_at: "2026-07-28T00:00:00Z",
};

function buildDummyCategoriesPlugin(enabled: boolean) {
  return {
    id: "asset-categories",
    name: "Asset Categories",
    version: "0.1.0",
    plugin_type: "community",
    capabilities: ["asset_provider", "metadata_provider", "option_provider"],
    extension_api_versions: [1],
    lifecycle_state: "running",
    diagnostic_reason: null,
    enabled,
    package_digest: "sha256:prototype-dummy-categories",
    created_at: "2026-07-28T00:09:00Z",
    updated_at: enabled ? "2026-07-28T00:10:00Z" : "2026-07-28T00:12:00Z",
  };
}

function createPrototypeState(): PrototypeState {
  return {
    collaborationState: {
      asset_id: "asset-1",
      state: "available",
      can_checkout: true,
      can_checkin: false,
      can_unlock: false,
      can_force_unlock: false,
      lock: null,
    },
    history: [initialRevision],
    timeline: [],
    notifications: {
      "user-owner": [],
      "user-member": [],
    },
    pluginEnabled: true,
    metadata: [],
  };
}

function getPrototypeState(page: Page): PrototypeState {
  let state = prototypeStates.get(page);
  if (!state) {
    state = createPrototypeState();
    prototypeStates.set(page, state);
  }
  return state;
}

export function createSharedPrototypeState(): PrototypeState {
  return createPrototypeState();
}

export async function mockPrototypeApi(
  page: Page,
  options: { state?: PrototypeState; user?: "owner" | "member" } = {},
) {
  const state = options.state ?? createPrototypeState();
  const currentUser = options.user === "member" ? memberUser : ownerUser;
  prototypeStates.set(page, state);

  await page.route("**/foundation", (route) => route.fulfill({
    json: { name: "OpenPDM", version: "0.0.0", phase: "Core Platform", architecture: "Modular Monolith" },
  }));
  await page.route("**/auth/session", (route) => route.fulfill({
    json: { id: `session-${currentUser.id}`, token: "token", user: currentUser },
  }));
  await page.route("**/organizations", (route) => route.fulfill({
    json: [{ id: `org-member-${currentUser.id}`, role: options.user === "member" ? "Member" : "Owner", user: currentUser, organization: { id: "org-1", name: "Prototype Org", slug: "prototype-org" } }],
  }));
  await page.route("**/organizations/org-1/projects/me", (route) => route.fulfill({
    json: [{ id: `project-member-${currentUser.id}`, role: options.user === "member" ? "Member" : "Owner", user: currentUser, project: { id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" } }],
  }));
  await page.route("**/organizations/org-1/projects", (route) => route.fulfill({
    json: [{ id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" }],
  }));
  await page.route("**/organizations/org-1/members", (route) => route.fulfill({
    json: [
      { id: "org-member-owner", role: "Owner", user: ownerUser, organization: { id: "org-1", name: "Prototype Org", slug: "prototype-org" } },
      { id: "org-member-member", role: "Member", user: memberUser, organization: { id: "org-1", name: "Prototype Org", slug: "prototype-org" } },
    ],
  }));
  await page.route("**/projects/project-1/members", (route) => {
    if (route.request().resourceType() !== "fetch") return route.fallback();
    return route.fulfill({
      json: [
        { id: "project-member-owner", role: "Owner", user: ownerUser, project: { id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" } },
        { id: "project-member-member", role: "Member", user: memberUser, project: { id: "project-1", organization_id: "org-1", name: "Prototype Project", description: "Local prototype", created_at: "2026-07-28T00:00:00Z" } },
      ],
    });
  });
  await page.route("**/projects/project-1/assets**", (route) => {
    if (route.request().resourceType() === "document") return route.fallback();
    return route.fulfill({
      json: {
        items: [{
          id: "asset-1",
          project_id: "project-1",
          name: "Prototype Asset",
          description: "Generic Engineering Asset",
          status: "draft",
          metadata: {},
          created_at: "2026-07-28T00:00:00Z",
        }, {
          id: "asset-2",
          project_id: "project-1",
          name: "Referenced Asset",
          description: "Outgoing graph neighbor",
          status: "draft",
          metadata: {},
          created_at: "2026-07-28T00:01:00Z",
        }, {
          id: "asset-3",
          project_id: "project-1",
          name: "Incoming Asset",
          description: "Incoming graph neighbor",
          status: "draft",
          metadata: {},
          created_at: "2026-07-28T00:02:00Z",
        }],
        next_cursor: null,
      },
    });
  });
  await page.route("**/assets/asset-1", (route) => route.fulfill({
    json: { id: "asset-1", project_id: "project-1", name: "Prototype Asset", description: "Generic Engineering Asset", status: "draft", metadata: {}, created_at: "2026-07-28T00:00:00Z" },
  }));
  await page.route("**/assets/asset-1/history", (route) => route.fulfill({
    json: state.history,
  }));
  await page.route("**/assets/asset-1/collaboration-state", (route) => route.fulfill({
    json: state.collaborationState,
  }));
  await page.route("**/assets/asset-1/timeline", (route) => route.fulfill({ json: state.timeline }));
  await page.route("**/notifications**", (route) => {
    if (route.request().resourceType() === "document") return route.fallback();
    if (route.request().url().includes("/read")) return route.fallback();
    const unreadOnly = route.request().url().includes("is_read=false");
    const items = state.notifications[currentUser.id] ?? [];
    return route.fulfill({
      json: {
        items: unreadOnly ? items.filter((item) => !item.is_read) : items,
        next_cursor: null,
      },
    });
  });
  await page.route("**/plugins", (route) => {
    if (route.request().resourceType() === "document") return route.fallback();
    const pathname = new URL(route.request().url()).pathname;
    if (!pathname.endsWith("/plugins")) return route.fallback();
    return route.fulfill({ json: [buildDummyCategoriesPlugin(state.pluginEnabled)] });
  });
  await page.route("**/plugins/asset-categories/state", async (route) => {
    const payload = await route.request().postDataJSON() as { enabled?: boolean };
    state.pluginEnabled = Boolean(payload.enabled);
    return route.fulfill({ json: buildDummyCategoriesPlugin(state.pluginEnabled) });
  });
  await page.route("**/plugins/asset-categories/providers/options", (route) => route.fulfill({
    json: [{
      key: "category",
      label: "Engineering Asset category",
      options: [
        { value: "document", label: "Document" },
        { value: "drawing", label: "Drawing" },
        { value: "model", label: "Model" },
        { value: "assembly", label: "Assembly" },
      ],
    }],
  }));
  await page.route("**/plugins/asset-categories/providers/metadata", async (route) => {
    const payload = await route.request().postDataJSON() as { parameters?: { category?: string } };
    const category = payload.parameters?.category ?? "document";
    const contributed = [{
      id: "metadata-category",
      asset_id: "asset-1",
      revision_id: null,
      representation_id: null,
      key: "classification.category",
      value: category,
      value_type: "string",
      source: "plugin:asset-categories",
      created_at: "2026-07-28T00:11:00Z",
    }, {
      id: "metadata-managed-by",
      asset_id: "asset-1",
      revision_id: null,
      representation_id: null,
      key: "classification.managed_by",
      value: "dummy-categories",
      value_type: "string",
      source: "plugin:asset-categories",
      created_at: "2026-07-28T00:11:00Z",
    }];
    state.metadata = contributed;
    return route.fulfill({ json: contributed });
  });
  await page.route("**/providers", (route) => route.fulfill({
    json: state.pluginEnabled
      ? [{
        id: "asset-categories",
        name: "Asset Categories",
        capabilities: ["asset_provider", "metadata_provider", "option_provider"],
      }]
      : [],
  }));
  await page.route("**/notifications/*/read", (route) => {
    const notificationId = route.request().url().split("/").at(-2);
    const items = state.notifications[currentUser.id] ?? [];
    const item = items.find((candidate) => candidate.id === notificationId);
    if (!item) {
      return route.fulfill({ status: 404, json: { detail: "Notification not found." } });
    }
    item.is_read = true;
    item.read_at = "2026-07-28T00:10:00Z";
    return route.fulfill({ json: item });
  });
  await page.route("**/assets/asset-1/relationships", (route) => route.fulfill({
    json: [{
      id: "rel-1",
      source_asset_id: "asset-1",
      target_asset_id: "asset-2",
      relationship_type: "depends_on",
      direction: "outgoing",
      metadata: { note: "Prototype dependency" },
      created_by_user_id: "user-owner",
      created_at: "2026-07-28T00:06:00Z",
    }],
  }));
  await page.route("**/assets/asset-1/relationships/incoming", (route) => route.fulfill({
    json: [{
      id: "rel-2",
      source_asset_id: "asset-3",
      target_asset_id: "asset-1",
      relationship_type: "references",
      direction: "incoming",
      metadata: {},
      created_by_user_id: "user-member",
      created_at: "2026-07-28T00:07:00Z",
    }],
  }));
  await page.route("**/assets/asset-1/relationships/outgoing", (route) => route.fulfill({
    json: [{
      id: "rel-1",
      source_asset_id: "asset-1",
      target_asset_id: "asset-2",
      relationship_type: "depends_on",
      direction: "outgoing",
      metadata: { note: "Prototype dependency" },
      created_by_user_id: "user-owner",
      created_at: "2026-07-28T00:06:00Z",
    }],
  }));
  await page.route("**/assets/asset-1/references", (route) => route.fulfill({
    json: [{
      id: "ref-1",
      source_asset_id: "asset-1",
      reference_type: "external_url",
      target_uri: "https://example.test/specification",
      label: "Supplier specification",
      metadata: {},
      created_by_user_id: "user-owner",
      created_at: "2026-07-28T00:08:00Z",
    }],
  }));
  await page.route("**/assets/asset-1/graph**", (route) => route.fulfill({
    json: {
      asset_id: "asset-1",
      direction: "both",
      max_depth: 3,
      target_asset_id: null,
      path_exists: null,
      has_cycle: false,
      nodes: [
        { id: "asset-1", project_id: "project-1", name: "Prototype Asset", status: "draft" },
        { id: "asset-2", project_id: "project-1", name: "Referenced Asset", status: "draft" },
        { id: "asset-3", project_id: "project-1", name: "Incoming Asset", status: "draft" },
      ],
      relationships: [],
    },
  }));
  await page.route("**/metadata/asset/asset-1", (route) => route.fulfill({ json: state.metadata }));
}

export async function mockPrototypeMutations(
  page: Page,
  options: { user?: "owner" | "member" } = {},
) {
  const state = getPrototypeState(page);
  const currentUserId = options.user === "member" ? "user-member" : "user-owner";
  const otherUserId = options.user === "member" ? "user-owner" : "user-member";

  await page.route("**/assets/asset-1/checkout", (route) => {
    if (state.collaborationState.lock && state.collaborationState.lock.owner_user_id !== currentUserId) {
      state.notifications[currentUserId].unshift({
        id: `notification-conflict-${currentUserId}`,
        recipient_user_id: currentUserId,
        actor_user_id: currentUserId,
        organization_id: "org-1",
        project_id: "project-1",
        asset_id: "asset-1",
        revision_id: null,
        event_type: "collaboration.conflict_detected",
        is_read: false,
        read_at: null,
        details: { user_guidance: "Refresh the Asset state before trying again." },
        created_at: "2026-07-28T00:03:00Z",
      });
      return route.fulfill({
        status: 409,
        json: {
          detail: {
            code: "asset_locked",
            message: "Asset is already locked.",
            user_guidance: "Refresh the Asset state before trying again.",
            recovery_action: "refresh_state",
          },
        },
      });
    }
    state.collaborationState = {
      asset_id: "asset-1",
      state: "locked",
      can_checkout: false,
      can_checkin: true,
      can_unlock: true,
      can_force_unlock: false,
      lock: { id: "lock-1", asset_id: "asset-1", owner_user_id: currentUserId, created_at: "2026-07-28T00:00:00Z" },
    };
    state.notifications[otherUserId].unshift({
      id: `notification-asset-locked-${otherUserId}`,
      recipient_user_id: otherUserId,
      actor_user_id: currentUserId,
      organization_id: "org-1",
      project_id: "project-1",
      asset_id: "asset-1",
      revision_id: null,
      event_type: "asset.checked_out",
      is_read: false,
      read_at: null,
      details: { asset_name: "Prototype Asset" },
      created_at: "2026-07-28T00:01:00Z",
    });
    return route.fulfill({ json: state.collaborationState });
  });
  await page.route("**/assets/asset-1/unlock", (route) => {
    state.collaborationState = {
      asset_id: "asset-1",
      state: "available",
      can_checkout: true,
      can_checkin: false,
      can_unlock: false,
      can_force_unlock: false,
      lock: null,
    };
    return route.fulfill({ json: state.collaborationState });
  });
  await page.route("**/blobs/upload-sessions", (route) => route.fulfill({
    json: {
      id: "session-1",
      asset_id: "asset-1",
      owner_user_id: "user-owner",
      filename: "sample.txt",
      media_type: "text/plain",
      total_size_bytes: 11,
      chunk_size_bytes: 11,
      checksum_sha256: null,
      status: "active",
      received_chunk_numbers: [],
      received_bytes: 0,
      blob: null,
      expires_at: "2026-07-29T00:00:00Z",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-28T00:00:00Z",
    },
  }));
  await page.route("**/blobs/upload-sessions/session-1/chunks/0", (route) => route.fulfill({
    json: {
      id: "session-1",
      asset_id: "asset-1",
      owner_user_id: "user-owner",
      filename: "sample.txt",
      media_type: "text/plain",
      total_size_bytes: 11,
      chunk_size_bytes: 11,
      checksum_sha256: null,
      status: "active",
      received_chunk_numbers: [0],
      received_bytes: 11,
      blob: null,
      expires_at: "2026-07-29T00:00:00Z",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-28T00:00:00Z",
    },
  }));
  await page.route("**/blobs/upload-sessions/session-1/complete", (route) => route.fulfill({
    json: {
      id: "session-1",
      asset_id: "asset-1",
      owner_user_id: "user-owner",
      filename: "sample.txt",
      media_type: "text/plain",
      total_size_bytes: 11,
      chunk_size_bytes: 11,
      checksum_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      status: "completed",
      received_chunk_numbers: [0],
      received_bytes: 11,
      blob: revisionBlob,
      expires_at: "2026-07-29T00:00:00Z",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-28T00:00:00Z",
    },
  }));
  await page.route("**/assets/asset-1/checkin", (route) => {
    state.history = [checkedInRevision, initialRevision];
    state.timeline = [{
      event_type: "revision.created",
      occurred_at: "2026-07-28T00:05:00Z",
      actor_user_id: "user-owner",
      asset_id: "asset-1",
      revision_id: "rev-2",
      details: { revision_number: 2, representation_name: "sample.txt" },
    }];
    state.collaborationState = {
      asset_id: "asset-1",
      state: "available",
      can_checkout: true,
      can_checkin: false,
      can_unlock: false,
      can_force_unlock: false,
      lock: null,
    };
    return route.fulfill({ json: checkedInRevision, status: 201 });
  });
  await page.route("**/blobs/blob-1/download", (route) => route.fulfill({
    body: "hello world",
    contentType: "text/plain",
  }));
}

export async function signInWithStoredSession(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("openpdm.sessionToken", "token");
    window.localStorage.setItem("openpdm.organizationId", "org-1");
    window.localStorage.setItem("openpdm.projectId", "project-1");
    window.localStorage.setItem("openpdm.assetId", "asset-1");
  });
}

export async function mockFirstRunPrototypeApi(page: Page) {
  const owner = {
    id: "user-owner",
    email: "prototype-owner@example.com",
    display_name: "Prototype Owner",
    is_active: true,
    is_platform_admin: true,
    created_at: "2026-07-28T00:00:00Z",
  };
  const organization = {
    id: "org-1",
    name: "Prototype Org",
    slug: "prototype-org",
  };
  const project = {
    id: "project-1",
    organization_id: "org-1",
    name: "Prototype Project",
    description: "Local prototype",
    created_at: "2026-07-28T00:00:00Z",
  };
  const asset = {
    id: "asset-1",
    project_id: "project-1",
    name: "Prototype Asset",
    description: "Generic Engineering Asset",
    status: "draft",
    metadata: {},
    created_at: "2026-07-28T00:00:00Z",
    updated_at: "2026-07-28T00:00:00Z",
  };
  const orgMembership = { id: "org-member-1", role: "Owner", user: owner, organization };
  const projectMembership = { id: "project-member-1", role: "Owner", user: owner, project };
  let hasOrganization = false;
  let hasProject = false;
  let hasAsset = false;

  await page.route("**/foundation", (route) => route.fulfill({
    json: { name: "OpenPDM", version: "0.0.0", phase: "Core Platform", architecture: "Modular Monolith" },
  }));
  await page.route("**/auth/register", (route) => route.fulfill({ json: owner, status: 201 }));
  await page.route("**/auth/sign-in", (route) => route.fulfill({
    json: { id: "session-1", token: "token", user: owner },
  }));
  await page.route("**/auth/session", (route) => route.fulfill({
    json: { id: "session-1", token: "token", user: owner },
  }));
  await page.route("**/organizations", (route) => {
    if (route.request().method() === "POST") {
      hasOrganization = true;
      return route.fulfill({ json: organization, status: 201 });
    }
    return route.fulfill({ json: hasOrganization ? [orgMembership] : [] });
  });
  await page.route("**/organizations/org-1/projects/me", (route) =>
    route.fulfill({ json: hasProject ? [projectMembership] : [] }));
  await page.route("**/organizations/org-1/projects", (route) =>
    route.fulfill({ json: hasProject ? [project] : [] }));
  await page.route("**/projects", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    hasProject = true;
    return route.fulfill({ json: project, status: 201 });
  });
  await page.route("**/projects/project-1/members", (route) => route.fulfill({
    json: hasProject ? [projectMembership] : [],
  }));
  await page.route("**/projects/project-1/assets**", (route) => {
    if (route.request().resourceType() === "document") return route.fallback();
    if (route.request().method() === "POST") {
      hasAsset = true;
      return route.fulfill({ json: asset, status: 201 });
    }
    return route.fulfill({ json: { items: hasAsset ? [asset] : [], next_cursor: null } });
  });
  await page.route("**/assets/asset-1", (route) => route.fulfill({ json: asset }));
  await page.route("**/assets/asset-1/history", (route) => route.fulfill({ json: [checkedInRevision, initialRevision] }));
  await page.route("**/assets/asset-1/collaboration-state", (route) => route.fulfill({
    json: {
      asset_id: "asset-1",
      state: "available",
      can_checkout: true,
      can_checkin: false,
      can_unlock: false,
      can_force_unlock: false,
      lock: null,
    },
  }));
  await page.route("**/assets/asset-1/timeline", (route) => route.fulfill({ json: [] }));
  await page.route("**/notifications**", (route) => {
    if (route.request().resourceType() === "document") return route.fallback();
    return route.fulfill({ json: { items: [], next_cursor: null } });
  });
  await page.route("**/providers", (route) => route.fulfill({ json: [] }));
  await page.route("**/relationships**", (route) => route.fulfill({ json: [] }));
  await page.route("**/references**", (route) => route.fulfill({ json: [] }));
  await page.route("**/assets/asset-1/graph**", (route) => route.fulfill({
    json: { root_asset_id: "asset-1", direction: "both", max_depth: 3, nodes: [], edges: [] },
  }));
  await page.route("**/metadata**", (route) => route.fulfill({ json: [] }));
  await page.route("**/users/me/project-views**", (route) => route.fulfill({ json: [] }));
  await page.route("**/blobs/blob-1/download", (route) => route.fulfill({
    body: "hello world",
    contentType: "text/plain",
  }));
}

export async function expectNoPageOverflow(page: Page) {
  const dimensions = await page.evaluate(() => {
    const root = document.documentElement;
    const overflowing = Array.from(document.querySelectorAll<HTMLElement>("*")).filter(
      (element) => element.getBoundingClientRect().right > root.clientWidth,
    ).map((element) => {
      const rect = element.getBoundingClientRect();
      return {
        className: element.className,
        minWidth: window.getComputedStyle(element).minWidth,
        right: Math.round(rect.right),
        tagName: element.tagName,
        width: Math.round(rect.width),
      };
    }).slice(0, 10);
    return { clientWidth: root.clientWidth, overflowing, scrollWidth: root.scrollWidth };
  });
  expect(dimensions.scrollWidth, JSON.stringify(dimensions.overflowing)).toBeLessThanOrEqual(dimensions.clientWidth);
}
