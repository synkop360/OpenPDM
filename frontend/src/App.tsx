import { startTransition, useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  checkinAsset,
  checkoutAsset,
  addRepresentation,
  createAsset,
  createOrganization,
  createProject,
  createRevision,
  downloadBlob,
  fetchFoundationStatus,
  getAsset,
  getAssetHistory,
  getAssetTimeline,
  getCollaborationState,
  getCurrentSession,
  listAssets,
  listOrganizationProjects,
  listOrganizations,
  listProjectsForUser,
  registerUser,
  signIn,
  signOut,
  unlockAsset,
  uploadBlob,
  type Asset,
  type CollaborationState,
  type FoundationStatus,
  type OrganizationMembership,
  type Project,
  type Revision,
  type SessionInfo,
  type TimelineEntry,
} from "./api";
import "./styles.css";

const SESSION_TOKEN_KEY = "openpdm.sessionToken";
const ORG_KEY = "openpdm.organizationId";
const PROJECT_KEY = "openpdm.projectId";
const ASSET_KEY = "openpdm.assetId";

type AuthMode = "sign-in" | "register";

type Loadable<T> = {
  status: "idle" | "loading" | "ready" | "error";
  data: T;
  error: string | null;
};

function createLoadable<T>(data: T): Loadable<T> {
  return { status: "idle", data, error: null };
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function readStoredValue(key: string): string | null {
  return window.localStorage.getItem(key);
}

function writeStoredValue(key: string, value: string | null): void {
  if (value) {
    window.localStorage.setItem(key, value);
    return;
  }
  window.localStorage.removeItem(key);
}

async function triggerBrowserDownload(
  token: string,
  blobId: string,
  filename: string,
): Promise<void> {
  const blob = await downloadBlob(token, blobId);
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

function collaborationGuidance(error: ApiError): string {
  const contextualGuidance = error.context?.user_guidance;
  if (typeof contextualGuidance === "string" && contextualGuidance.trim()) {
    return contextualGuidance;
  }
  switch (error.code) {
    case "asset_locked":
      return "This Asset is already locked by another user. Wait for release or ask a Maintainer to coordinate.";
    case "checkin_without_lock":
      return "Check out the Asset before checking in changes.";
    case "checkin_by_non_owner":
      return "Only the current lock owner can check in changes for this Asset.";
    case "unlock_not_allowed":
      return "Only the lock owner can unlock this Asset unless a Maintainer or Owner force-unlocks.";
    case "asset_archived":
      return "Archived Assets cannot be changed through the collaboration flow.";
    case "no_active_lock":
      return "This Asset no longer has an active collaboration lock. Refresh the state and try again if needed.";
    default:
      return error.message;
  }
}

function collaborationRecoveryAction(error: ApiError): string | null {
  const value = error.context?.recovery_action;
  return typeof value === "string" ? value : null;
}

function collaborationRequestId(error: ApiError): string | null {
  const value = error.context?.request_id;
  return typeof value === "string" ? value : null;
}

function collaborationShouldRefresh(error: ApiError): boolean {
  return error.context?.should_refresh === true;
}

export function App() {
  const [foundation, setFoundation] = useState<Loadable<FoundationStatus | null>>(
    createLoadable<FoundationStatus | null>(null),
  );
  const [session, setSession] = useState<Loadable<SessionInfo | null>>(
    createLoadable<SessionInfo | null>(null),
  );
  const [organizations, setOrganizations] = useState<Loadable<OrganizationMembership[]>>(
    createLoadable<OrganizationMembership[]>([]),
  );
  const [projects, setProjects] = useState<Loadable<Project[]>>(createLoadable<Project[]>([]));
  const [assets, setAssets] = useState<Loadable<Asset[]>>(createLoadable<Asset[]>([]));
  const [assetDetail, setAssetDetail] = useState<Loadable<Asset | null>>(
    createLoadable<Asset | null>(null),
  );
  const [assetHistory, setAssetHistory] = useState<Loadable<Revision[]>>(
    createLoadable<Revision[]>([]),
  );
  const [collaborationState, setCollaborationState] = useState<Loadable<CollaborationState | null>>(
    createLoadable<CollaborationState | null>(null),
  );
  const [assetTimeline, setAssetTimeline] = useState<Loadable<TimelineEntry[]>>(
    createLoadable<TimelineEntry[]>([]),
  );
  const [collaborationError, setCollaborationError] = useState<ApiError | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("sign-in");
  const [authError, setAuthError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [authForm, setAuthForm] = useState({
    email: "",
    password: "",
    displayName: "",
  });
  const [bootstrapOrg, setBootstrapOrg] = useState({ name: "", slug: "" });
  const [bootstrapProject, setBootstrapProject] = useState({ name: "", description: "" });
  const [assetForm, setAssetForm] = useState({ name: "", description: "" });
  const [uploadForm, setUploadForm] = useState({
    file: null as File | null,
    comment: "",
    representationName: "",
  });
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(
    readStoredValue(ORG_KEY),
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(readStoredValue(PROJECT_KEY));
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(readStoredValue(ASSET_KEY));

  useEffect(() => {
    setFoundation((current) => ({ ...current, status: "loading", error: null }));
    fetchFoundationStatus()
      .then((result) => {
        setFoundation({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setFoundation({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Unknown API error",
        });
      });
  }, []);

  useEffect(() => {
    const token = readStoredValue(SESSION_TOKEN_KEY);
    if (!token) {
      setSession({ status: "ready", data: null, error: null });
      return;
    }
    setSession((current) => ({ ...current, status: "loading", error: null }));
    getCurrentSession(token)
      .then((result) => {
        setSession({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        writeStoredValue(SESSION_TOKEN_KEY, null);
        setSession({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Session could not be restored.",
        });
      });
  }, []);

  useEffect(() => {
    const token = session.data?.token;
    if (!token) {
      setOrganizations(createLoadable([]));
      setProjects(createLoadable([]));
      setAssets(createLoadable([]));
      setAssetDetail(createLoadable(null));
      setAssetHistory(createLoadable([]));
      setCollaborationState(createLoadable(null));
      setAssetTimeline(createLoadable([]));
      setCollaborationError(null);
      return;
    }
    setOrganizations((current) => ({ ...current, status: "loading", error: null }));
    listOrganizations(token)
      .then((result) => {
        setOrganizations({ status: "ready", data: result, error: null });
        if (result.length === 0) {
          startTransition(() => {
            setSelectedOrganizationId(null);
            setSelectedProjectId(null);
            setSelectedAssetId(null);
          });
          return;
        }

        const fallbackOrganizationId = result[0].organization?.id ?? null;
        const nextOrganizationId =
          result.find((item) => item.organization?.id === selectedOrganizationId)?.organization?.id ??
          fallbackOrganizationId;
        startTransition(() => {
          setSelectedOrganizationId(nextOrganizationId);
        });
      })
      .catch((error: unknown) => {
        setOrganizations({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Organizations could not be loaded.",
        });
      });
  }, [session.data?.token, selectedOrganizationId]);

  useEffect(() => {
    writeStoredValue(ORG_KEY, selectedOrganizationId);
  }, [selectedOrganizationId]);

  useEffect(() => {
    writeStoredValue(PROJECT_KEY, selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    writeStoredValue(ASSET_KEY, selectedAssetId);
  }, [selectedAssetId]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedOrganizationId) {
      setProjects(createLoadable([]));
      return;
    }
    setProjects((current) => ({ ...current, status: "loading", error: null }));
    Promise.all([
      listProjectsForUser(token, selectedOrganizationId),
      listOrganizationProjects(token, selectedOrganizationId),
    ])
      .then(([memberships, organizationProjects]) => {
        const membershipProjects = memberships.flatMap((item) => (item.project ? [item.project] : []));
        const merged = [...organizationProjects];
        for (const item of membershipProjects) {
          if (!merged.some((project) => project.id === item.id)) {
            merged.push(item);
          }
        }
        setProjects({ status: "ready", data: merged, error: null });
        const nextProjectId =
          merged.find((project) => project.id === selectedProjectId)?.id ?? merged[0]?.id ?? null;
        startTransition(() => {
          setSelectedProjectId(nextProjectId);
        });
      })
      .catch((error: unknown) => {
        setProjects({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Projects could not be loaded.",
        });
      });
  }, [selectedOrganizationId, selectedProjectId, session.data?.token]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedProjectId) {
      setAssets(createLoadable([]));
      setSelectedAssetId(null);
      return;
    }
    setAssets((current) => ({ ...current, status: "loading", error: null }));
    listAssets(token, selectedProjectId)
      .then((result) => {
        setAssets({ status: "ready", data: result, error: null });
        const nextAssetId = result.find((asset) => asset.id === selectedAssetId)?.id ?? result[0]?.id ?? null;
        startTransition(() => {
          setSelectedAssetId(nextAssetId);
        });
      })
      .catch((error: unknown) => {
        setAssets({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Assets could not be loaded.",
        });
      });
  }, [selectedAssetId, selectedProjectId, session.data?.token]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedAssetId) {
      setAssetDetail(createLoadable(null));
      setAssetHistory(createLoadable([]));
      setCollaborationState(createLoadable(null));
      setAssetTimeline(createLoadable([]));
      return;
    }
    setAssetDetail((current) => ({ ...current, status: "loading", error: null }));
    setAssetHistory((current) => ({ ...current, status: "loading", error: null }));
    setCollaborationState((current) => ({ ...current, status: "loading", error: null }));
    setAssetTimeline((current) => ({ ...current, status: "loading", error: null }));
    getAsset(token, selectedAssetId)
      .then((result) => {
        setAssetDetail({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setAssetDetail({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Asset details could not be loaded.",
        });
      });
    getAssetHistory(token, selectedAssetId)
      .then((result) => {
        setAssetHistory({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setAssetHistory({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Revision history could not be loaded.",
        });
      });
    getCollaborationState(token, selectedAssetId)
      .then((result) => {
        setCollaborationState({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setCollaborationState({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Collaboration state could not be loaded.",
        });
      });
    getAssetTimeline(token, selectedAssetId)
      .then((result) => {
        setAssetTimeline({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setAssetTimeline({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Collaboration timeline could not be loaded.",
        });
      });
  }, [selectedAssetId, session.data?.token]);

  const isAuthenticated = Boolean(session.data?.token);
  const hasOrganizations = organizations.data.length > 0;
  const hasProjects = projects.data.length > 0;
  const hasAssets = assets.data.length > 0;

  async function handleRegister(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusyAction("register");
    setAuthError(null);
    setBanner(null);
    try {
      await registerUser({
        email: authForm.email,
        display_name: authForm.displayName,
        password: authForm.password,
      });
      const nextSession = await signIn({
        email: authForm.email,
        password: authForm.password,
      });
      writeStoredValue(SESSION_TOKEN_KEY, nextSession.token);
      setSession({ status: "ready", data: nextSession, error: null });
      setBanner("Account created and signed in.");
    } catch (error: unknown) {
      setAuthError(error instanceof Error ? error.message : "Registration failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSignIn(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusyAction("sign-in");
    setAuthError(null);
    setBanner(null);
    try {
      const nextSession = await signIn({
        email: authForm.email,
        password: authForm.password,
      });
      writeStoredValue(SESSION_TOKEN_KEY, nextSession.token);
      setSession({ status: "ready", data: nextSession, error: null });
      setBanner("Signed in.");
    } catch (error: unknown) {
      setAuthError(error instanceof Error ? error.message : "Sign-in failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSignOut(): Promise<void> {
    if (!session.data?.token) {
      return;
    }
    setBusyAction("sign-out");
    setBanner(null);
    try {
      await signOut(session.data.token);
    } catch {
      // Clear local session even if remote sign-out fails.
    } finally {
      writeStoredValue(SESSION_TOKEN_KEY, null);
      writeStoredValue(ORG_KEY, null);
      writeStoredValue(PROJECT_KEY, null);
      writeStoredValue(ASSET_KEY, null);
      setSelectedOrganizationId(null);
      setSelectedProjectId(null);
      setSelectedAssetId(null);
      setSession({ status: "ready", data: null, error: null });
      setBusyAction(null);
      setBanner("Signed out.");
    }
  }

  async function handleBootstrapOrganization(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token) {
      return;
    }
    setBusyAction("create-organization");
    setBanner(null);
    try {
      const organization = await createOrganization(session.data.token, {
        name: bootstrapOrg.name,
        slug: bootstrapOrg.slug || slugify(bootstrapOrg.name),
      });
      setBootstrapOrg({ name: "", slug: "" });
      setSelectedOrganizationId(organization.id);
      setBanner("Organization created.");
      const refreshed = await listOrganizations(session.data.token);
      setOrganizations({ status: "ready", data: refreshed, error: null });
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Organization could not be created.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleBootstrapProject(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token || !selectedOrganizationId) {
      return;
    }
    setBusyAction("create-project");
    setBanner(null);
    try {
      const project = await createProject(session.data.token, {
        organization_id: selectedOrganizationId,
        name: bootstrapProject.name,
        description: bootstrapProject.description,
      });
      setBootstrapProject({ name: "", description: "" });
      setSelectedProjectId(project.id);
      setBanner("Project created.");
      const refreshed = await listOrganizationProjects(session.data.token, selectedOrganizationId);
      setProjects({ status: "ready", data: refreshed, error: null });
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Project could not be created.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateAsset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token || !selectedProjectId) {
      return;
    }
    setBusyAction("create-asset");
    setBanner(null);
    try {
      const asset = await createAsset(session.data.token, selectedProjectId, assetForm);
      setAssetForm({ name: "", description: "" });
      setSelectedAssetId(asset.id);
      setBanner("Engineering Asset created.");
      const refreshed = await listAssets(session.data.token, selectedProjectId);
      setAssets({ status: "ready", data: refreshed, error: null });
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Asset could not be created.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token || !selectedAssetId || !uploadForm.file) {
      return;
    }
    setBusyAction("upload");
    setBanner(null);
    setCollaborationError(null);
    try {
      const blob = await uploadBlob(session.data.token, uploadForm.file);
      await checkinAsset(session.data.token, selectedAssetId, {
        comment: uploadForm.comment,
        representations: [
          {
            name: uploadForm.representationName || uploadForm.file.name,
            media_type: uploadForm.file.type || "application/octet-stream",
            blob_id: blob.id,
          },
        ],
      });
      setUploadForm({ file: null, comment: "", representationName: "" });
      setBanner("Changes checked in as a new immutable Revision.");
      const [nextAsset, nextHistory, nextCollaborationState, nextTimeline] = await Promise.all([
        getAsset(session.data.token, selectedAssetId),
        getAssetHistory(session.data.token, selectedAssetId),
        getCollaborationState(session.data.token, selectedAssetId),
        getAssetTimeline(session.data.token, selectedAssetId),
      ]);
      setAssetDetail({ status: "ready", data: nextAsset, error: null });
      setAssetHistory({ status: "ready", data: nextHistory, error: null });
      setCollaborationState({ status: "ready", data: nextCollaborationState, error: null });
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      const refreshed = await listAssets(session.data.token, selectedProjectId!);
      setAssets({ status: "ready", data: refreshed, error: null });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setCollaborationError(error);
        setBanner(collaborationGuidance(error));
      } else {
        setBanner(error instanceof Error ? error.message : "Upload failed.");
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCheckout(): Promise<void> {
    if (!session.data?.token || !selectedAssetId) {
      return;
    }
    setBusyAction("checkout");
    setBanner(null);
    setCollaborationError(null);
    try {
      const nextState = await checkoutAsset(session.data.token, selectedAssetId);
      setCollaborationState({ status: "ready", data: nextState, error: null });
      const nextTimeline = await getAssetTimeline(session.data.token, selectedAssetId);
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      setBanner("Asset checked out for collaboration.");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setCollaborationError(error);
        setBanner(collaborationGuidance(error));
      } else {
        setBanner(error instanceof Error ? error.message : "Checkout failed.");
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUnlock(force: boolean): Promise<void> {
    if (!session.data?.token || !selectedAssetId) {
      return;
    }
    setBusyAction(force ? "force-unlock" : "unlock");
    setBanner(null);
    setCollaborationError(null);
    try {
      const nextState = await unlockAsset(session.data.token, selectedAssetId, { force });
      setCollaborationState({ status: "ready", data: nextState, error: null });
      const nextTimeline = await getAssetTimeline(session.data.token, selectedAssetId);
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      setBanner(force ? "Asset force-unlocked." : "Asset unlocked.");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setCollaborationError(error);
        setBanner(collaborationGuidance(error));
      } else {
        setBanner(error instanceof Error ? error.message : "Unlock failed.");
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRefreshAssetState(): Promise<void> {
    if (!session.data?.token || !selectedAssetId || !selectedProjectId) {
      return;
    }
    setBusyAction("refresh-state");
    setBanner(null);
    try {
      const [nextAsset, nextHistory, nextCollaborationState, nextTimeline, refreshedAssets] =
        await Promise.all([
          getAsset(session.data.token, selectedAssetId),
          getAssetHistory(session.data.token, selectedAssetId),
          getCollaborationState(session.data.token, selectedAssetId),
          getAssetTimeline(session.data.token, selectedAssetId),
          listAssets(session.data.token, selectedProjectId),
        ]);
      setAssetDetail({ status: "ready", data: nextAsset, error: null });
      setAssetHistory({ status: "ready", data: nextHistory, error: null });
      setCollaborationState({ status: "ready", data: nextCollaborationState, error: null });
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      setAssets({ status: "ready", data: refreshedAssets, error: null });
      setCollaborationError(null);
      setBanner("Collaboration state refreshed.");
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDownload(blobId: string, filename: string): Promise<void> {
    if (!session.data?.token) {
      return;
    }
    setBusyAction(`download-${blobId}`);
    setBanner(null);
    try {
      await triggerBrowserDownload(session.data.token, blobId, filename);
      setBanner(`Download started for ${filename}.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Download failed.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Core Platform MVP</p>
          <h1>OpenPDM Web UI Prototype</h1>
          <p className="intro">
            The Web UI is a normal public API consumer for the Phase 1 Platform Core. This prototype
            covers sign-in, Organization and Project access, generic Engineering Asset browsing, immutable
            Revision history, and Blob-backed upload and download.
          </p>
        </div>
        <dl className="foundation-grid">
          <div>
            <dt>API Status</dt>
            <dd>{foundation.data ? foundation.data.phase : foundation.error ?? "Loading..."}</dd>
          </div>
          <div>
            <dt>Architecture</dt>
            <dd>{foundation.data?.architecture ?? "Connecting..."}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{foundation.data?.version ?? "Unknown"}</dd>
          </div>
        </dl>
      </section>

      {banner ? (
        <p className="banner" role="status">
          {banner}
        </p>
      ) : null}

      {!isAuthenticated ? (
        <section className="panel auth-panel">
          <header className="panel-header">
            <div>
              <p className="eyebrow">Access</p>
              <h2>{authMode === "sign-in" ? "Sign in" : "Create your first local user"}</h2>
            </div>
            <div className="segmented-control" role="tablist" aria-label="Authentication mode">
              <button
                className={authMode === "sign-in" ? "is-active" : ""}
                onClick={() => setAuthMode("sign-in")}
                type="button"
              >
                Sign in
              </button>
              <button
                className={authMode === "register" ? "is-active" : ""}
                onClick={() => setAuthMode("register")}
                type="button"
              >
                Register
              </button>
            </div>
          </header>

          <form
            className="form-grid"
            onSubmit={authMode === "sign-in" ? handleSignIn : handleRegister}
          >
            {authMode === "register" ? (
              <label>
                Display name
                <input
                  required
                  value={authForm.displayName}
                  onChange={(event) =>
                    setAuthForm((current) => ({ ...current, displayName: event.target.value }))
                  }
                />
              </label>
            ) : null}
            <label>
              Email
              <input
                required
                type="email"
                value={authForm.email}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, email: event.target.value }))
                }
              />
            </label>
            <label>
              Password
              <input
                required
                type="password"
                value={authForm.password}
                onChange={(event) =>
                  setAuthForm((current) => ({ ...current, password: event.target.value }))
                }
              />
            </label>
            {authError ? (
              <p className="error-message" role="alert">
                {authError}
              </p>
            ) : null}
            {session.error ? (
              <p className="error-message" role="alert">
                {session.error}
              </p>
            ) : null}
            <button className="primary-button" disabled={busyAction !== null} type="submit">
              {busyAction === "sign-in"
                ? "Signing in..."
                : busyAction === "register"
                  ? "Creating account..."
                  : authMode === "sign-in"
                    ? "Sign in"
                    : "Create account"}
            </button>
          </form>
        </section>
      ) : (
        <>
          <section className="panel session-panel">
            <header className="panel-header">
              <div>
                <p className="eyebrow">Session</p>
                <h2>{session.data?.user.display_name}</h2>
                <p className="muted-text">{session.data?.user.email}</p>
              </div>
              <button className="secondary-button" onClick={() => void handleSignOut()} type="button">
                {busyAction === "sign-out" ? "Signing out..." : "Sign out"}
              </button>
            </header>
          </section>

          <section className="workspace-grid">
            <section className="panel nav-panel">
              <header className="panel-header">
                <div>
                  <p className="eyebrow">Workspace</p>
                  <h2>Organizations and Projects</h2>
                </div>
              </header>

              {organizations.status === "error" ? (
                <p className="error-message" role="alert">
                  {organizations.error}
                </p>
              ) : null}

              {!hasOrganizations ? (
                <form className="form-grid compact-form" onSubmit={handleBootstrapOrganization}>
                  <h3>Create your first Organization</h3>
                  <label>
                    Organization name
                    <input
                      required
                      value={bootstrapOrg.name}
                      onChange={(event) =>
                        setBootstrapOrg((current) => ({
                          ...current,
                          name: event.target.value,
                          slug: current.slug || slugify(event.target.value),
                        }))
                      }
                    />
                  </label>
                  <label>
                    Slug
                    <input
                      required
                      value={bootstrapOrg.slug}
                      onChange={(event) =>
                        setBootstrapOrg((current) => ({ ...current, slug: event.target.value }))
                      }
                    />
                  </label>
                  <button
                    className="primary-button"
                    disabled={busyAction === "create-organization"}
                    type="submit"
                  >
                    {busyAction === "create-organization" ? "Creating..." : "Create Organization"}
                  </button>
                </form>
              ) : (
                <>
                  <div className="resource-list">
                    <h3>Organizations</h3>
                    {organizations.data.map((membership) => {
                      const organization = membership.organization;
                      if (!organization) {
                        return null;
                      }
                      return (
                        <button
                          key={membership.id}
                          className={
                            selectedOrganizationId === organization.id
                              ? "resource-card is-selected"
                              : "resource-card"
                          }
                          onClick={() => setSelectedOrganizationId(organization.id)}
                          type="button"
                        >
                          <strong>{organization.name}</strong>
                          <span>{membership.role}</span>
                          <small>{organization.slug}</small>
                        </button>
                      );
                    })}
                  </div>

                  {selectedOrganizationId && !hasProjects ? (
                    <form className="form-grid compact-form" onSubmit={handleBootstrapProject}>
                      <h3>Create the first Project</h3>
                      <label>
                        Project name
                        <input
                          required
                          value={bootstrapProject.name}
                          onChange={(event) =>
                            setBootstrapProject((current) => ({ ...current, name: event.target.value }))
                          }
                        />
                      </label>
                      <label>
                        Description
                        <textarea
                          value={bootstrapProject.description}
                          onChange={(event) =>
                            setBootstrapProject((current) => ({
                              ...current,
                              description: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <button
                        className="primary-button"
                        disabled={busyAction === "create-project"}
                        type="submit"
                      >
                        {busyAction === "create-project" ? "Creating..." : "Create Project"}
                      </button>
                    </form>
                  ) : null}

                  {projects.status === "error" ? (
                    <p className="error-message" role="alert">
                      {projects.error}
                    </p>
                  ) : null}

                  {hasProjects ? (
                    <div className="resource-list">
                      <h3>Projects</h3>
                      {projects.data.map((project) => (
                        <button
                          key={project.id}
                          className={
                            selectedProjectId === project.id ? "resource-card is-selected" : "resource-card"
                          }
                          onClick={() => setSelectedProjectId(project.id)}
                          type="button"
                        >
                          <strong>{project.name}</strong>
                          <span>{project.description || "No description"}</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </>
              )}
            </section>

            <section className="panel asset-panel">
              <header className="panel-header">
                <div>
                  <p className="eyebrow">Engineering Assets</p>
                  <h2>Project content</h2>
                </div>
              </header>

              {selectedProjectId ? (
                <>
                  <form className="form-grid compact-form" onSubmit={handleCreateAsset}>
                    <h3>Create a generic Engineering Asset</h3>
                    <label>
                      Asset name
                      <input
                        required
                        value={assetForm.name}
                        onChange={(event) =>
                          setAssetForm((current) => ({ ...current, name: event.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Description
                      <textarea
                        value={assetForm.description}
                        onChange={(event) =>
                          setAssetForm((current) => ({ ...current, description: event.target.value }))
                        }
                      />
                    </label>
                    <button
                      className="primary-button"
                      disabled={busyAction === "create-asset"}
                      type="submit"
                    >
                      {busyAction === "create-asset" ? "Creating..." : "Create Asset"}
                    </button>
                  </form>

                  {assets.status === "error" ? (
                    <p className="error-message" role="alert">
                      {assets.error}
                    </p>
                  ) : null}

                  {hasAssets ? (
                    <div className="resource-list">
                      <h3>Assets</h3>
                      {assets.data.map((asset) => (
                        <button
                          key={asset.id}
                          className={selectedAssetId === asset.id ? "resource-card is-selected" : "resource-card"}
                          onClick={() => setSelectedAssetId(asset.id)}
                          type="button"
                        >
                          <strong>{asset.name}</strong>
                          <span>{asset.status}</span>
                          <small>{asset.description || "No description"}</small>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-state">
                      Create the first Engineering Asset to unlock immutable Revision history and file transfer.
                    </p>
                  )}
                </>
              ) : (
                <p className="empty-state">Select a Project to browse or create Engineering Assets.</p>
              )}
            </section>

            <section className="panel detail-panel">
              <header className="panel-header">
                <div>
                  <p className="eyebrow">Lifecycle</p>
                  <h2>Asset detail and Revision history</h2>
                </div>
              </header>

              {selectedAssetId && assetDetail.data ? (
                <>
                  <article className="detail-card">
                    <div className="detail-row">
                      <div>
                        <h3>{assetDetail.data.name}</h3>
                        <p>{assetDetail.data.description || "No description."}</p>
                      </div>
                      <span className="status-pill">{assetDetail.data.status}</span>
                    </div>
                    <p className="muted-text">
                      Created {formatTimestamp(assetDetail.data.created_at)} and updated{" "}
                      {formatTimestamp(assetDetail.data.updated_at)}.
                    </p>
                  </article>

                  <article className="detail-card collaboration-card">
                    <div className="detail-row">
                      <div>
                        <h3>Collaboration state</h3>
                        <p>
                          {collaborationState.data
                            ? `State: ${collaborationState.data.state}`
                            : "Loading collaboration state..."}
                        </p>
                      </div>
                      <span
                        className={`status-pill collaboration-pill collaboration-${collaborationState.data?.state ?? "unknown"}`}
                      >
                        {collaborationState.data?.state ?? "loading"}
                      </span>
                    </div>
                    {collaborationState.data?.lock ? (
                      <p className="muted-text">
                        Lock owner:{" "}
                        {collaborationState.data.lock.owner_user_id === session.data?.user.id
                          ? "You"
                          : collaborationState.data.lock.owner_user_id}
                      </p>
                    ) : (
                      <p className="muted-text">No active collaboration lock.</p>
                    )}
                    <div className="collaboration-actions">
                      <button
                        className="primary-button"
                        disabled={busyAction === "checkout" || collaborationState.data?.state === "locked"}
                        onClick={() => void handleCheckout()}
                        type="button"
                      >
                        {busyAction === "checkout" ? "Checking out..." : "Check out"}
                      </button>
                      <button
                        className="secondary-button"
                        disabled={busyAction === "unlock" || !collaborationState.data?.can_unlock}
                        onClick={() => void handleUnlock(false)}
                        type="button"
                      >
                        {busyAction === "unlock" ? "Unlocking..." : "Unlock"}
                      </button>
                      <button
                        className="secondary-button warning-button"
                        disabled={busyAction === "force-unlock" || !collaborationState.data?.can_force_unlock}
                        onClick={() => void handleUnlock(true)}
                        type="button"
                      >
                        {busyAction === "force-unlock" ? "Force-unlocking..." : "Force unlock"}
                      </button>
                    </div>
                  </article>

                  <form className="form-grid compact-form" onSubmit={handleUpload}>
                    <h3>Check in a new Revision</h3>
                    <label>
                      Revision comment
                      <input
                        required
                        value={uploadForm.comment}
                        onChange={(event) =>
                          setUploadForm((current) => ({ ...current, comment: event.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Representation name
                      <input
                        value={uploadForm.representationName}
                        onChange={(event) =>
                          setUploadForm((current) => ({
                            ...current,
                            representationName: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      File
                      <input
                        required
                        type="file"
                        onChange={(event) =>
                          setUploadForm((current) => ({
                            ...current,
                            file: event.target.files?.[0] ?? null,
                            representationName:
                              current.representationName || event.target.files?.[0]?.name || "",
                          }))
                        }
                      />
                    </label>
                    <button
                      className="primary-button"
                      disabled={busyAction === "upload" || !collaborationState.data?.can_checkin}
                      type="submit"
                    >
                      {busyAction === "upload" ? "Checking in..." : "Check in revision"}
                    </button>
                    <p className="muted-text">
                      Check-in is available only while you own the collaboration lock.
                    </p>
                  </form>

                  {collaborationState.status === "error" ? (
                    <p className="error-message" role="alert">
                      {collaborationState.error}
                    </p>
                  ) : null}

                  {collaborationError ? (
                    <article className="detail-card recovery-card">
                      <h3>Recovery guidance</h3>
                      <p>{collaborationGuidance(collaborationError)}</p>
                      {collaborationRequestId(collaborationError) ? (
                        <p className="muted-text">
                          Request ID: {collaborationRequestId(collaborationError)}
                        </p>
                      ) : null}
                      <div className="collaboration-actions">
                        {collaborationShouldRefresh(collaborationError) ? (
                          <button
                            className="secondary-button"
                            disabled={busyAction === "refresh-state"}
                            onClick={() => void handleRefreshAssetState()}
                            type="button"
                          >
                            {busyAction === "refresh-state" ? "Refreshing..." : "Refresh asset state"}
                          </button>
                        ) : null}
                        {collaborationRecoveryAction(collaborationError) === "checkout_asset" ? (
                          <button
                            className="secondary-button"
                            disabled={
                              busyAction === "checkout" || collaborationState.data?.state === "locked"
                            }
                            onClick={() => void handleCheckout()}
                            type="button"
                          >
                            Check out now
                          </button>
                        ) : null}
                      </div>
                    </article>
                  ) : null}

                  {assetTimeline.status === "error" ? (
                    <p className="error-message" role="alert">
                      {assetTimeline.error}
                    </p>
                  ) : null}

                  <div className="timeline">
                    <h3>Collaboration timeline</h3>
                    {assetTimeline.data.map((entry) => (
                      <article
                        key={`${entry.event_type}-${entry.occurred_at}-${entry.revision_id ?? "none"}`}
                        className="timeline-card"
                      >
                        <div className="timeline-header">
                          <div>
                            <h3>{entry.event_type}</h3>
                            <p>
                              {entry.actor_user_id === session.data?.user.id
                                ? "You"
                                : entry.actor_user_id ?? "System"}
                            </p>
                          </div>
                          <small>{formatTimestamp(entry.occurred_at)}</small>
                        </div>
                        {entry.revision_id ? (
                          <p className="muted-text">Revision: {entry.revision_id}</p>
                        ) : null}
                      </article>
                    ))}
                  </div>

                  {assetHistory.status === "error" ? (
                    <p className="error-message" role="alert">
                      {assetHistory.error}
                    </p>
                  ) : null}

                  <div className="timeline">
                    <h3>Revision comments and history</h3>
                    {assetHistory.data.map((revision) => (
                      <article key={revision.id} className="timeline-card">
                        <div className="timeline-header">
                          <div>
                            <h3>Revision {revision.number}</h3>
                            <p>{revision.comment || "No revision comment."}</p>
                          </div>
                          <small>{formatTimestamp(revision.created_at)}</small>
                        </div>
                        {revision.representations.length > 0 ? (
                          <ul className="representation-list">
                            {revision.representations.map((representation) => (
                              <li key={representation.id}>
                                <div>
                                  <strong>{representation.name}</strong>
                                  <span>{representation.media_type}</span>
                                  <small>{representation.blob?.filename ?? "No Blob attached"}</small>
                                </div>
                                {representation.blob_id && representation.blob ? (
                                  <button
                                    className="secondary-button"
                                    disabled={busyAction === `download-${representation.blob_id}`}
                                    onClick={() =>
                                      void handleDownload(
                                        representation.blob_id!,
                                        representation.blob?.filename ?? `${representation.name}.bin`,
                                      )
                                    }
                                    type="button"
                                  >
                                    {busyAction === `download-${representation.blob_id}`
                                      ? "Preparing..."
                                      : "Download"}
                                  </button>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted-text">No Representations for this Revision yet.</p>
                        )}
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <p className="empty-state">
                  Select an Engineering Asset to inspect immutable Revision history and Blob-backed
                  Representations.
                </p>
              )}
            </section>
          </section>
        </>
      )}
    </main>
  );
}

export default App;
