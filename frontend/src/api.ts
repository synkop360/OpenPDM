const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
  /\/$/,
  "",
) ?? "";

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export type Page<T> = {
  items: T[];
  next_cursor: string | null;
};

export type PageOptions = {
  limit?: number;
  cursor?: string;
  sort?: string;
  direction?: "asc" | "desc";
};

function collectionUrl(path: string, options: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return query.size ? path + "?" + query.toString() : path;
}

export type FoundationStatus = {
  name: string;
  version: string;
  phase: string;
  architecture: string;
};

export type User = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_platform_admin: boolean;
  created_at: string;
};

export type PluginRecord = {
  id: string;
  name: string;
  version: string;
  plugin_type: "official" | "community";
  capabilities: string[];
  extension_api_versions: number[];
  lifecycle_state: string;
  diagnostic_reason: string | null;
  enabled: boolean;
  package_digest: string;
  created_at: string;
  updated_at: string;
};

export type PluginConfiguration = {
  plugin_id: string;
  configuration_schema: Record<string, unknown> | null;
  values: Record<string, unknown>;
  configured_secret_fields: string[];
  updated_at: string | null;
};

export type ProviderDescriptor = {
  id: string;
  name: string;
  capabilities: string[];
};

export type ProviderOptionSet = {
  key: string;
  label: string;
  options: Array<{ value: string; label: string }>;
};

export type MetadataEntry = {
  id: string;
  asset_id: string | null;
  revision_id: string | null;
  representation_id: string | null;
  key: string;
  value: unknown;
  value_type: string;
  source: string;
  created_at: string;
};

export type SessionInfo = {
  id: string;
  token: string;
  user: User;
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
  created_at: string;
};

export type OrganizationMembership = {
  id: string;
  role: string;
  organization: Organization | null;
  user?: User | null;
};

export type Project = {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  created_at: string;
};

export type ProjectMembership = {
  id: string;
  role: string;
  project: Project | null;
  user?: User | null;
};

export type BlobRecord = {
  id: string;
  storage_key: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  created_at: string;
};

export type BlobUploadSession = {
  id: string;
  filename: string;
  media_type: string;
  total_size_bytes: number;
  checksum_sha256: string | null;
  chunk_size_bytes: number;
  status: "active" | "completed" | "cancelled" | "expired";
  received_bytes: number;
  received_chunk_numbers: number[];
  expires_at: string;
  created_at: string;
  updated_at: string;
  blob: BlobRecord | null;
};

export type CreateBlobUploadSessionPayload = {
  filename: string;
  media_type: string;
  total_size_bytes: number;
  checksum_sha256?: string | null;
};

export type Representation = {
  id: string;
  revision_id: string;
  name: string;
  media_type: string;
  blob_id: string | null;
  created_at: string;
  blob: BlobRecord | null;
};

export type Revision = {
  id: string;
  asset_id: string;
  number: number;
  comment: string;
  created_by_user_id: string;
  created_at: string;
  representations: Representation[];
};

export type CollaborationLock = {
  id: string;
  asset_id: string;
  owner_user_id: string;
  created_at: string;
};

export type CollaborationState = {
  asset_id: string;
  state: "available" | "locked" | "stale_lock";
  can_checkin: boolean;
  can_unlock: boolean;
  can_force_unlock: boolean;
  lock: CollaborationLock | null;
};

export type TimelineEntry = {
  event_type: string;
  occurred_at: string;
  actor_user_id: string | null;
  asset_id: string;
  revision_id: string | null;
  details: Record<string, unknown>;
};

export type ProjectAssetView = {
  id: string;
  project_id: string;
  name: string;
  filters: Record<string, unknown>;
  sort: { field: string; direction: "asc" | "desc" };
  density: "compact" | "comfortable";
  selected_columns: string[];
  created_at: string;
  updated_at: string;
};

export type ProjectAssetViewInput = {
  project_id: string;
  name: string;
  filters: Record<string, unknown>;
  sort: { field: string; direction: "asc" | "desc" };
  density: "compact" | "comfortable";
  selected_columns: string[];
};

export type NotificationRecord = {
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
};

export type Relationship = {
  id: string;
  source_asset_id: string;
  target_asset_id: string;
  relationship_type: string;
  direction: string;
  metadata: Record<string, unknown>;
  created_by_user_id: string;
  created_at: string;
};

export type ReferenceRecord = {
  id: string;
  source_asset_id: string;
  reference_type: string;
  target_uri: string;
  label: string;
  metadata: Record<string, unknown>;
  created_by_user_id: string;
  created_at: string;
};

export type GraphNode = {
  id: string;
  project_id: string;
  name: string;
  status: string;
};

export type AssetGraph = {
  asset_id: string;
  direction: string;
  max_depth: number;
  target_asset_id: string | null;
  path_exists: boolean | null;
  has_cycle: boolean;
  nodes: GraphNode[];
  relationships: Relationship[];
};

export type Asset = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  status: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  revisions: Revision[];
};

export class ApiError extends Error {
  status: number;
  code?: string;
  context?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string, context?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.context = context;
  }
}

type RequestOptions = {
  method?: string;
  token?: string | null;
  body?: BodyInit | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  const response = await fetch(apiUrl(path), {
    method: options.method ?? "GET",
    body: options.body,
    headers,
    signal: options.signal,
  });
  if (!response.ok) {
    let message = `OpenPDM API request failed with status ${response.status}`;
    let code: string | undefined;
    let context: Record<string, unknown> | undefined;
    try {
      const payload = (await response.json()) as {
        detail?:
          | string
          | {
              code?: string;
              message?: string;
              context?: Record<string, unknown>;
            };
      };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail) {
        message = payload.detail.message ?? message;
        code = payload.detail.code;
        context = payload.detail.context;
      }
    } catch {
      // Keep the default status-based message when the response is not JSON.
    }
    throw new ApiError(message, response.status, code, context);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) {
    throw new ApiError(
      `OpenPDM API routing error: expected JSON but received ${contentType || "an unknown content type"}`,
      response.status,
      "invalid_api_response",
    );
  }
  return response.json() as Promise<T>;
}

export async function fetchFoundationStatus(): Promise<FoundationStatus> {
  return request<FoundationStatus>("/foundation");
}

export async function registerUser(payload: {
  email: string;
  display_name: string;
  password: string;
}): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function signIn(payload: {
  email: string;
  password: string;
}): Promise<SessionInfo> {
  return request<SessionInfo>("/auth/sign-in", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function getCurrentSession(token: string): Promise<SessionInfo> {
  return request<SessionInfo>("/auth/session", { token });
}

export async function signOut(token: string): Promise<SessionInfo> {
  return request<SessionInfo>("/auth/sign-out", {
    method: "POST",
    token,
  });
}

export async function listOrganizations(token: string): Promise<OrganizationMembership[]> {
  return request<OrganizationMembership[]>("/organizations", { token });
}

export async function createOrganization(
  token: string,
  payload: { name: string; slug: string },
): Promise<Organization> {
  return request<Organization>("/organizations", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function listOrganizationMembers(
  token: string,
  organizationId: string,
): Promise<OrganizationMembership[]> {
  return request<OrganizationMembership[]>(`/organizations/${organizationId}/members`, { token });
}

export async function addOrganizationMember(
  token: string,
  organizationId: string,
  payload: { user_email: string; role: string },
): Promise<OrganizationMembership> {
  return request<OrganizationMembership>(`/organizations/${organizationId}/members`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function changeOrganizationMemberRole(
  token: string,
  organizationId: string,
  membershipId: string,
  role: string,
): Promise<OrganizationMembership> {
  return request<OrganizationMembership>(
    `/organizations/${organizationId}/members/${membershipId}`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ role }),
      headers: { "Content-Type": "application/json" },
    },
  );
}

export async function removeOrganizationMember(
  token: string,
  organizationId: string,
  membershipId: string,
): Promise<void> {
  await request<void>(`/organizations/${organizationId}/members/${membershipId}`, {
    method: "DELETE",
    token,
  });
}

export async function listProjectsForUser(
  token: string,
  organizationId: string,
): Promise<ProjectMembership[]> {
  return request<ProjectMembership[]>(`/organizations/${organizationId}/projects/me`, { token });
}

export async function listOrganizationProjects(
  token: string,
  organizationId: string,
): Promise<Project[]> {
  return request<Project[]>(`/organizations/${organizationId}/projects`, { token });
}

export async function createProject(
  token: string,
  payload: { organization_id: string; name: string; description: string },
): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function listProjectMembers(
  token: string,
  projectId: string,
): Promise<ProjectMembership[]> {
  return request<ProjectMembership[]>(`/projects/${projectId}/members`, { token });
}

export async function addProjectMember(
  token: string,
  projectId: string,
  payload: { user_id: string; role: string },
): Promise<ProjectMembership> {
  return request<ProjectMembership>(`/projects/${projectId}/members`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function changeProjectMemberRole(
  token: string,
  projectId: string,
  membershipId: string,
  role: string,
): Promise<ProjectMembership> {
  return request<ProjectMembership>(`/projects/${projectId}/members/${membershipId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ role }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function removeProjectMember(
  token: string,
  projectId: string,
  membershipId: string,
): Promise<void> {
  await request<void>(`/projects/${projectId}/members/${membershipId}`, {
    method: "DELETE",
    token,
  });
}

export async function listAssets(token: string, projectId: string): Promise<Asset[]> {
  return request<Asset[]>(`/projects/${projectId}/assets`, { token });
}

export async function getAsset(token: string, assetId: string): Promise<Asset> {
  return request<Asset>(`/assets/${assetId}`, { token });
}

export async function getAssetHistory(token: string, assetId: string): Promise<Revision[]> {
  return request<Revision[]>(`/assets/${assetId}/history`, { token });
}

export async function createAsset(
  token: string,
  projectId: string,
  payload: { name: string; description: string },
): Promise<Asset> {
  return request<Asset>(`/projects/${projectId}/assets`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function createRevision(
  token: string,
  assetId: string,
  payload: { comment: string },
): Promise<Revision> {
  return request<Revision>(`/assets/${assetId}/revisions`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function getCollaborationState(
  token: string,
  assetId: string,
): Promise<CollaborationState> {
  return request<CollaborationState>(`/assets/${assetId}/collaboration-state`, { token });
}

export async function checkoutAsset(token: string, assetId: string): Promise<CollaborationState> {
  return request<CollaborationState>(`/assets/${assetId}/checkout`, {
    method: "POST",
    token,
  });
}

export async function unlockAsset(
  token: string,
  assetId: string,
  payload: { force: boolean },
): Promise<CollaborationState> {
  return request<CollaborationState>(`/assets/${assetId}/unlock`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function checkinAsset(
  token: string,
  assetId: string,
  payload: {
    comment: string;
    representations: Array<{ name: string; media_type: string; blob_id: string | null }>;
  },
): Promise<Revision> {
  return request<Revision>(`/assets/${assetId}/checkin`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function getAssetTimeline(token: string, assetId: string): Promise<TimelineEntry[]> {
  return request<TimelineEntry[]>(`/assets/${assetId}/timeline`, { token });
}

export async function listAssetRelationships(token: string, assetId: string): Promise<Relationship[]> {
  return request<Relationship[]>(`/assets/${assetId}/relationships`, { token });
}

export async function listIncomingAssetRelationships(
  token: string,
  assetId: string,
): Promise<Relationship[]> {
  return request<Relationship[]>(`/assets/${assetId}/relationships/incoming`, { token });
}

export async function listOutgoingAssetRelationships(
  token: string,
  assetId: string,
): Promise<Relationship[]> {
  return request<Relationship[]>(`/assets/${assetId}/relationships/outgoing`, { token });
}

export async function listAssetReferences(token: string, assetId: string): Promise<ReferenceRecord[]> {
  return request<ReferenceRecord[]>(`/assets/${assetId}/references`, { token });
}

export async function getAssetGraph(
  token: string,
  assetId: string,
  options?: { direction?: "incoming" | "outgoing" | "both"; maxDepth?: number; targetAssetId?: string },
): Promise<AssetGraph> {
  const query = new URLSearchParams();
  if (options?.direction) {
    query.set("direction", options.direction);
  }
  if (options?.maxDepth !== undefined) {
    query.set("max_depth", String(options.maxDepth));
  }
  if (options?.targetAssetId) {
    query.set("target_asset_id", options.targetAssetId);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return request<AssetGraph>(`/assets/${assetId}/graph${suffix}`, { token });
}

export async function listNotifications(token: string): Promise<NotificationRecord[]> {
  return request<NotificationRecord[]>("/notifications", { token });
}

export async function markNotificationRead(
  token: string,
  notificationId: string,
): Promise<NotificationRecord> {
  return request<NotificationRecord>(`/notifications/${notificationId}/read`, {
    method: "POST",
    token,
  });
}

export async function listPlugins(token: string): Promise<PluginRecord[]> {
  return request<PluginRecord[]>("/plugins", { token });
}

export async function discoverProviders(token: string): Promise<ProviderDescriptor[]> {
  return request<ProviderDescriptor[]>("/providers", { token });
}

export async function getProviderOptions(
  token: string,
  pluginId: string,
  projectId: string,
  organizationId: string,
): Promise<ProviderOptionSet[]> {
  return request<ProviderOptionSet[]>(`/plugins/${pluginId}/providers/options`, {
    method: "POST",
    token,
    body: JSON.stringify({ payload: { project_id: projectId }, organization_id: organizationId }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function invokeMetadataProvider(
  token: string,
  pluginId: string,
  payload: {
    target_type: "asset";
    target_id: string;
    project_id: string;
    organization_id: string;
    parameters: Record<string, unknown>;
  },
): Promise<MetadataEntry[]> {
  return request<MetadataEntry[]>(`/plugins/${pluginId}/providers/metadata`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function listMetadata(
  token: string,
  targetType: "asset",
  targetId: string,
): Promise<MetadataEntry[]> {
  return request<MetadataEntry[]>(`/metadata/${targetType}/${targetId}`, { token });
}

export async function installPluginPackage(
  token: string,
  packageFile: File,
  pluginType: "official" | "community" = "community",
): Promise<PluginRecord> {
  const formData = new FormData();
  formData.append("package", packageFile);
  return request<PluginRecord>(`/plugins/packages?plugin_type=${pluginType}`, {
    method: "POST",
    token,
    body: formData,
  });
}

export async function setPluginState(
  token: string,
  pluginId: string,
  enabled: boolean,
): Promise<PluginRecord> {
  return request<PluginRecord>(`/plugins/${pluginId}/state`, {
    method: "POST",
    token,
    body: JSON.stringify({ enabled }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function upgradePluginPackage(
  token: string,
  pluginId: string,
  packageFile: File,
): Promise<PluginRecord> {
  const formData = new FormData();
  formData.append("package", packageFile);
  return request<PluginRecord>(`/plugins/${pluginId}/package`, {
    method: "PUT",
    token,
    body: formData,
  });
}

export async function getPluginConfiguration(
  token: string,
  pluginId: string,
): Promise<PluginConfiguration> {
  return request<PluginConfiguration>(`/plugins/${pluginId}/configuration`, { token });
}

export async function updatePluginConfiguration(
  token: string,
  pluginId: string,
  values: Record<string, unknown>,
): Promise<PluginConfiguration> {
  return request<PluginConfiguration>(`/plugins/${pluginId}/configuration`, {
    method: "PUT",
    token,
    body: JSON.stringify({ values }),
    headers: { "Content-Type": "application/json" },
  });
}

export async function removePlugin(token: string, pluginId: string): Promise<void> {
  await request<void>(`/plugins/${pluginId}`, { method: "DELETE", token });
}

export async function uploadBlob(token: string, file: File): Promise<BlobRecord> {
  const formData = new FormData();
  formData.append("file", file);
  return request<BlobRecord>("/blobs/uploads", {
    method: "POST",
    token,
    body: formData,
  });
}

export async function createBlobUploadSession(
  token: string,
  payload: CreateBlobUploadSessionPayload,
  signal?: AbortSignal,
): Promise<BlobUploadSession> {
  return request<BlobUploadSession>("/blobs/upload-sessions", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    signal,
  });
}

export async function getBlobUploadSession(token: string, sessionId: string, signal?: AbortSignal): Promise<BlobUploadSession> {
  return request<BlobUploadSession>(`/blobs/upload-sessions/${sessionId}`, { token, signal });
}

export async function putBlobUploadChunk(
  token: string,
  sessionId: string,
  chunkNumber: number,
  content: Blob,
  signal?: AbortSignal,
): Promise<BlobUploadSession> {
  return request<BlobUploadSession>(`/blobs/upload-sessions/${sessionId}/chunks/${chunkNumber}`, {
    method: "PUT",
    token,
    body: content,
    headers: { "Content-Type": "application/octet-stream" },
    signal,
  });
}

export async function completeBlobUploadSession(token: string, sessionId: string, signal?: AbortSignal): Promise<BlobUploadSession> {
  return request<BlobUploadSession>(`/blobs/upload-sessions/${sessionId}/complete`, {
    method: "POST",
    token,
    signal,
  });
}

export async function cancelBlobUploadSession(token: string, sessionId: string): Promise<void> {
  await request<void>(`/blobs/upload-sessions/${sessionId}`, { method: "DELETE", token });
}

export async function addRepresentation(
  token: string,
  revisionId: string,
  payload: { name: string; media_type: string; blob_id: string | null },
): Promise<Representation> {
  return request<Representation>(`/revisions/${revisionId}/representations`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function downloadBlob(token: string, blobId: string): Promise<Blob> {
  const response = await fetch(apiUrl(`/blobs/${blobId}/download`), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new ApiError(`OpenPDM API request failed with status ${response.status}`, response.status);
  }
  return response.blob();
}

export async function listOrganizationMembersPage(
  token: string,
  organizationId: string,
  options: PageOptions & { role?: string; query?: string } = {},
): Promise<Page<OrganizationMembership>> {
  return request<Page<OrganizationMembership>>(
    collectionUrl("/organizations/" + organizationId + "/members/page", {
      limit: options.limit,
      cursor: options.cursor,
      role: options.role,
      q: options.query,
      sort: options.sort,
      direction: options.direction,
    }),
    { token },
  );
}

export async function listProjectMembersPage(
  token: string,
  projectId: string,
  options: PageOptions & { role?: string; query?: string } = {},
): Promise<Page<ProjectMembership>> {
  return request<Page<ProjectMembership>>(
    collectionUrl("/projects/" + projectId + "/members/page", {
      limit: options.limit,
      cursor: options.cursor,
      role: options.role,
      q: options.query,
      sort: options.sort,
      direction: options.direction,
    }),
    { token },
  );
}

export async function listAssetsPage(
  token: string,
  projectId: string,
  options: PageOptions & { status?: string; query?: string } = {},
): Promise<Page<Asset>> {
  const result = await request<Page<Asset> | Asset[]>(
    collectionUrl("/projects/" + projectId + "/assets/page", {
      limit: options.limit,
      cursor: options.cursor,
      status: options.status,
      q: options.query,
      sort: options.sort,
      direction: options.direction,
    }),
    { token },
  );
  return Array.isArray(result) ? { items: result, next_cursor: null } : result;
}
export async function listNotificationsPage(
  token: string,
  options: PageOptions & { projectId?: string; isRead?: boolean } = {},
): Promise<Page<NotificationRecord>> {
  const result = await request<Page<NotificationRecord> | NotificationRecord[]>(
    collectionUrl("/notifications/page", {
      limit: options.limit,
      cursor: options.cursor,
      project_id: options.projectId,
      is_read: options.isRead,
      sort: options.sort,
      direction: options.direction,
    }),
    { token },
  );
  return Array.isArray(result) ? { items: result, next_cursor: null } : result;
}
export async function markNotificationsRead(
  token: string,
  payload:
    | { notification_ids: string[]; all_matching?: false }
    | { notification_ids?: never; all_matching: true; project_id?: string; is_read?: boolean },
): Promise<{ updated_count: number; notification_ids: string[] }> {
  return request<{ updated_count: number; notification_ids: string[] }>("/notifications/read", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function listPluginsPage(
  token: string,
  options: PageOptions & {
    lifecycleState?: string;
    enabled?: boolean;
    query?: string;
  } = {},
): Promise<Page<PluginRecord>> {
  return request<Page<PluginRecord>>(
    collectionUrl("/plugins/page", {
      limit: options.limit,
      cursor: options.cursor,
      lifecycle_state: options.lifecycleState,
      enabled: options.enabled,
      q: options.query,
      sort: options.sort,
      direction: options.direction,
    }),
    { token },
  );
}

export async function listProjectAssetViews(
  token: string,
  projectId?: string,
): Promise<ProjectAssetView[]> {
  return request<ProjectAssetView[]>(
    collectionUrl("/users/me/project-views", { project_id: projectId }),
    { token },
  );
}

export async function createProjectAssetView(
  token: string,
  payload: ProjectAssetViewInput,
): Promise<ProjectAssetView> {
  return request<ProjectAssetView>("/users/me/project-views", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function updateProjectAssetView(
  token: string,
  viewId: string,
  payload: Omit<ProjectAssetViewInput, "project_id">,
): Promise<ProjectAssetView> {
  return request<ProjectAssetView>("/users/me/project-views/" + viewId, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function deleteProjectAssetView(token: string, viewId: string): Promise<void> {
  await request<void>("/users/me/project-views/" + viewId, { method: "DELETE", token });
}
