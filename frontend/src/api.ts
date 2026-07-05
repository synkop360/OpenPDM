const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
  /\/$/,
  "",
) ?? "";

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
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

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type RequestOptions = {
  method?: string;
  token?: string | null;
  body?: BodyInit | null;
  headers?: Record<string, string>;
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
  });
  if (!response.ok) {
    let message = `OpenPDM API request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Keep the default status-based message when the response is not JSON.
    }
    throw new ApiError(message, response.status);
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

export async function uploadBlob(token: string, file: File): Promise<BlobRecord> {
  const formData = new FormData();
  formData.append("file", file);
  return request<BlobRecord>("/blobs/uploads", {
    method: "POST",
    token,
    body: formData,
  });
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
