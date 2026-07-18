import { startTransition, useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  Bell,
  Boxes,
  ChevronRight,
  FolderKanban,
  Home,
  LogOut,
  Menu,
  Network,
  Package,
  Users,
  X,
} from "lucide-react";
import { BrowserRouter, useLocation, useNavigate } from "react-router-dom";
import {
  ApiError,
  addOrganizationMember,
  addProjectMember,
  type AssetGraph,
  checkinAsset,
  checkoutAsset,
  addRepresentation,
  createAsset,
  createOrganization,
  createProject,
  createRevision,
  changeOrganizationMemberRole,
  changeProjectMemberRole,
  downloadBlob,
  discoverProviders,
  fetchFoundationStatus,
  getAsset,
  getAssetGraph,
  getAssetHistory,
  getAssetTimeline,
  getCollaborationState,
  getCurrentSession,
  getPluginConfiguration,
  getProviderOptions,
  installPluginPackage,
  listAssetReferences,
  listAssetRelationships,
  listAssets,
  listIncomingAssetRelationships,
  listMetadata,
  listNotifications,
  listOrganizationProjects,
  listOrganizationMembers,
  listOutgoingAssetRelationships,
  listPlugins,
  listOrganizations,
  listProjectsForUser,
  listProjectMembers,
  markNotificationRead,
  invokeMetadataProvider,
  registerUser,
  removeOrganizationMember,
  removeProjectMember,
  removePlugin,
  setPluginState,
  signIn,
  signOut,
  type ReferenceRecord,
  type Relationship,
  unlockAsset,
  uploadBlob,
  type Asset,
  type CollaborationState,
  type FoundationStatus,
  type NotificationRecord,
  type OrganizationMembership,
  type Project,
  type ProjectMembership,
  type PluginRecord,
  type ProviderDescriptor,
  type ProviderOptionSet,
  type MetadataEntry,
  type Revision,
  type SessionInfo,
  type TimelineEntry,
  updatePluginConfiguration,
  upgradePluginPackage,
} from "./api";
import "./styles.css";

const SESSION_TOKEN_KEY = "openpdm.sessionToken";
const ORG_KEY = "openpdm.organizationId";
const PROJECT_KEY = "openpdm.projectId";
const ASSET_KEY = "openpdm.assetId";

type AuthMode = "sign-in" | "register";
type AppView = "home" | "projects" | "project" | "plugin-administration";
type ProjectTab = "overview" | "assets" | "relationships" | "collaboration" | "members";

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

function formatNotificationEvent(eventType: string): string {
  switch (eventType) {
    case "asset.checked_out":
      return "Asset locked";
    case "asset.unlocked":
      return "Asset unlocked";
    case "asset.force_unlocked":
      return "Force unlock";
    case "revision.created":
      return "Revision created";
    case "collaboration.conflict_detected":
      return "Conflict detected";
    default:
      return eventType;
  }
}

function notificationSummary(notification: NotificationRecord): string {
  if (notification.event_type === "collaboration.conflict_detected") {
    const guidance = notification.details.user_guidance;
    if (typeof guidance === "string" && guidance.trim()) {
      return guidance;
    }
  }
  const assetId = typeof notification.asset_id === "string" ? notification.asset_id : null;
  if (assetId) {
    return `Related Asset: ${assetId}`;
  }
  return "Project collaboration update.";
}

function formatRelationshipType(value: string): string {
  return value.replace(/_/g, " ");
}

function formatMetadataSummary(metadata: Record<string, unknown>): string | null {
  const entries = Object.entries(metadata);
  if (entries.length === 0) {
    return null;
  }
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" • ");
}

function OpenPdmApp() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeParts = location.pathname.split("/").filter(Boolean);
  const view: AppView =
    routeParts[0] === "administration" && routeParts[1] === "plugins"
      ? "plugin-administration"
      : routeParts[0] === "projects"
        ? routeParts.length >= 2
          ? "project"
          : "projects"
        : "home";
  const projectTab: ProjectTab = ([
    "overview",
    "assets",
    "relationships",
    "collaboration",
    "members",
  ] as ProjectTab[]).includes(routeParts[2] as ProjectTab)
    ? (routeParts[2] as ProjectTab)
    : "overview";
  const routeProjectId = view === "project" ? routeParts[1] : null;
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
  const [organizationMembers, setOrganizationMembers] = useState<Loadable<OrganizationMembership[]>>(
    createLoadable<OrganizationMembership[]>([]),
  );
  const [projectMembers, setProjectMembers] = useState<Loadable<ProjectMembership[]>>(
    createLoadable<ProjectMembership[]>([]),
  );
  const [assets, setAssets] = useState<Loadable<Asset[]>>(createLoadable<Asset[]>([]));
  const [assetDetail, setAssetDetail] = useState<Loadable<Asset | null>>(
    createLoadable<Asset | null>(null),
  );
  const [assetHistory, setAssetHistory] = useState<Loadable<Revision[]>>(
    createLoadable<Revision[]>([]),
  );
  const [assetRelationships, setAssetRelationships] = useState<Loadable<Relationship[]>>(
    createLoadable<Relationship[]>([]),
  );
  const [incomingRelationships, setIncomingRelationships] = useState<Loadable<Relationship[]>>(
    createLoadable<Relationship[]>([]),
  );
  const [outgoingRelationships, setOutgoingRelationships] = useState<Loadable<Relationship[]>>(
    createLoadable<Relationship[]>([]),
  );
  const [assetReferences, setAssetReferences] = useState<Loadable<ReferenceRecord[]>>(
    createLoadable<ReferenceRecord[]>([]),
  );
  const [assetGraph, setAssetGraph] = useState<Loadable<AssetGraph | null>>(
    createLoadable<AssetGraph | null>(null),
  );
  const [collaborationState, setCollaborationState] = useState<Loadable<CollaborationState | null>>(
    createLoadable<CollaborationState | null>(null),
  );
  const [assetTimeline, setAssetTimeline] = useState<Loadable<TimelineEntry[]>>(
    createLoadable<TimelineEntry[]>([]),
  );
  const [notifications, setNotifications] = useState<Loadable<NotificationRecord[]>>(
    createLoadable<NotificationRecord[]>([]),
  );
  const [plugins, setPlugins] = useState<Loadable<PluginRecord[]>>(createLoadable<PluginRecord[]>([]));
  const [providers, setProviders] = useState<Loadable<ProviderDescriptor[]>>(
    createLoadable<ProviderDescriptor[]>([]),
  );
  const [providerOptions, setProviderOptions] = useState<Record<string, ProviderOptionSet[]>>({});
  const [providerSelections, setProviderSelections] = useState<Record<string, string>>({});
  const [assetMetadata, setAssetMetadata] = useState<Loadable<MetadataEntry[]>>(
    createLoadable<MetadataEntry[]>([]),
  );
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [pluginPackage, setPluginPackage] = useState<File | null>(null);
  const [pluginConfiguration, setPluginConfiguration] = useState<Record<string, string>>({});
  const [pluginUpgradePackages, setPluginUpgradePackages] = useState<Record<string, File | null>>({});
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
  const [organizationMemberForm, setOrganizationMemberForm] = useState({
    email: "",
    role: "Viewer",
  });
  const [projectMemberForm, setProjectMemberForm] = useState({ userId: "", role: "Viewer" });
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
    if (routeProjectId && routeProjectId !== selectedProjectId) {
      setSelectedProjectId(routeProjectId);
    }
  }, [routeProjectId, selectedProjectId]);

  useEffect(() => {
    if (
      view === "project" &&
      routeProjectId &&
      projects.status === "ready" &&
      !projects.data.some((project) => project.id === routeProjectId)
    ) {
      navigate("/projects", { replace: true });
    }
  }, [navigate, projects.data, projects.status, routeProjectId, view]);

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
      setOrganizationMembers(createLoadable([]));
      setProjectMembers(createLoadable([]));
      setAssets(createLoadable([]));
      setAssetDetail(createLoadable(null));
      setAssetHistory(createLoadable([]));
      setAssetRelationships(createLoadable([]));
      setIncomingRelationships(createLoadable([]));
      setOutgoingRelationships(createLoadable([]));
      setAssetReferences(createLoadable([]));
      setAssetGraph(createLoadable(null));
      setCollaborationState(createLoadable(null));
      setAssetTimeline(createLoadable([]));
      setNotifications(createLoadable([]));
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
    const token = session.data?.token;
    if (!token || !selectedOrganizationId || view !== "project" || projectTab !== "members") {
      setOrganizationMembers(createLoadable([]));
      return;
    }
    setOrganizationMembers((current) => ({ ...current, status: "loading", error: null }));
    listOrganizationMembers(token, selectedOrganizationId)
      .then((result) => setOrganizationMembers({ status: "ready", data: result, error: null }))
      .catch((error: unknown) =>
        setOrganizationMembers({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Organization members could not be loaded.",
        }),
      );
  }, [projectTab, session.data?.token, selectedOrganizationId, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedProjectId || view !== "project") {
      setProjectMembers(createLoadable([]));
      return;
    }
    setProjectMembers((current) => ({ ...current, status: "loading", error: null }));
    listProjectMembers(token, selectedProjectId)
      .then((result) => setProjectMembers({ status: "ready", data: result, error: null }))
      .catch((error: unknown) =>
        setProjectMembers({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Project members could not be loaded.",
        }),
      );
  }, [session.data?.token, selectedProjectId, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token) {
      setNotifications(createLoadable([]));
      return;
    }
    setNotifications((current) => ({ ...current, status: "loading", error: null }));
    listNotifications(token)
      .then((result) => {
        setNotifications({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setNotifications({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Notifications could not be loaded.",
        });
      });
  }, [session.data?.token]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || view !== "plugin-administration" || !session.data?.user.is_platform_admin) {
      setPlugins(createLoadable([]));
      return;
    }
    setPlugins((current) => ({ ...current, status: "loading", error: null }));
    listPlugins(token)
      .then((result) => setPlugins({ status: "ready", data: result, error: null }))
      .catch((error: unknown) =>
        setPlugins({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Plugins could not be loaded.",
        }),
      );
  }, [session.data?.token, session.data?.user.is_platform_admin, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token) {
      setProviders(createLoadable([]));
      return;
    }
    discoverProviders(token)
      .then(async (result) => {
        setProviders({ status: "ready", data: result, error: null });
        if (!selectedProjectId || !selectedOrganizationId) return;
        const optionProviders = result.filter((provider) =>
          provider.capabilities.includes("option_provider"),
        );
        const entries = await Promise.all(
          optionProviders.map(async (provider) => [
            provider.id,
            await getProviderOptions(
              token,
              provider.id,
              selectedProjectId,
              selectedOrganizationId,
            ),
          ] as const),
        );
        setProviderOptions(Object.fromEntries(entries));
      })
      .catch((error: unknown) =>
        setProviders({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Providers could not be discovered.",
        }),
      );
  }, [selectedOrganizationId, selectedProjectId, session.data?.token]);

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
    if (!token || !selectedProjectId || view !== "project") {
      setAssets(createLoadable([]));
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
  }, [selectedAssetId, selectedProjectId, session.data?.token, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedAssetId || view !== "project") {
      setAssetDetail(createLoadable(null));
      setAssetHistory(createLoadable([]));
      setAssetRelationships(createLoadable([]));
      setIncomingRelationships(createLoadable([]));
      setOutgoingRelationships(createLoadable([]));
      setAssetReferences(createLoadable([]));
      setAssetGraph(createLoadable(null));
      setCollaborationState(createLoadable(null));
      setAssetTimeline(createLoadable([]));
      return;
    }
    setAssetDetail((current) => ({ ...current, status: "loading", error: null }));
    setAssetHistory((current) => ({ ...current, status: "loading", error: null }));
    setAssetRelationships((current) => ({ ...current, status: "loading", error: null }));
    setIncomingRelationships((current) => ({ ...current, status: "loading", error: null }));
    setOutgoingRelationships((current) => ({ ...current, status: "loading", error: null }));
    setAssetReferences((current) => ({ ...current, status: "loading", error: null }));
    setAssetGraph((current) => ({ ...current, status: "loading", error: null }));
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
    listAssetRelationships(token, selectedAssetId)
      .then((result) => {
        setAssetRelationships({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setAssetRelationships({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Relationships could not be loaded.",
        });
      });
    listIncomingAssetRelationships(token, selectedAssetId)
      .then((result) => {
        setIncomingRelationships({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setIncomingRelationships({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Incoming relationships could not be loaded.",
        });
      });
    listOutgoingAssetRelationships(token, selectedAssetId)
      .then((result) => {
        setOutgoingRelationships({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setOutgoingRelationships({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Outgoing relationships could not be loaded.",
        });
      });
    listAssetReferences(token, selectedAssetId)
      .then((result) => {
        setAssetReferences({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setAssetReferences({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "References could not be loaded.",
        });
      });
    getAssetGraph(token, selectedAssetId, { direction: "both", maxDepth: 3 })
      .then((result) => {
        setAssetGraph({ status: "ready", data: result, error: null });
      })
      .catch((error: unknown) => {
        setAssetGraph({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Graph summary could not be loaded.",
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
    listMetadata(token, "asset", selectedAssetId)
      .then((result) => setAssetMetadata({ status: "ready", data: result, error: null }))
      .catch((error: unknown) =>
        setAssetMetadata({
          status: "error",
          data: [],
          error: error instanceof Error ? error.message : "Asset metadata could not be loaded.",
        }),
      );
  }, [selectedAssetId, session.data?.token, view]);

  const isAuthenticated = Boolean(session.data?.token);
  const hasOrganizations = organizations.data.length > 0;
  const hasProjects = projects.data.length > 0;
  const currentOrganizationRole = organizations.data.find(
    (membership) => membership.organization?.id === selectedOrganizationId,
  )?.role;
  const currentProjectRole = projectMembers.data.find(
    (membership) => membership.user?.id === session.data?.user.id,
  )?.role;
  const canManageOrganizationMembers =
    currentOrganizationRole === "Owner" || currentOrganizationRole === "Maintainer";
  const canManageProjectMembers = currentProjectRole === "Owner" || currentProjectRole === "Maintainer";
  const hasAssets = assets.data.length > 0;
  const unreadNotifications = notifications.data.filter((item) => !item.is_read).length;
  const assetNameById = new Map(assets.data.map((asset) => [asset.id, asset.name]));

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

  async function refreshMemberships(): Promise<void> {
    if (!session.data?.token || !selectedOrganizationId) {
      return;
    }
    const refreshedOrganizations = await listOrganizations(session.data.token);
    setOrganizations({ status: "ready", data: refreshedOrganizations, error: null });
    const refreshedOrganizationMembers = await listOrganizationMembers(
      session.data.token,
      selectedOrganizationId,
    );
    setOrganizationMembers({ status: "ready", data: refreshedOrganizationMembers, error: null });
    if (selectedProjectId) {
      const refreshedProjectMembers = await listProjectMembers(session.data.token, selectedProjectId);
      setProjectMembers({ status: "ready", data: refreshedProjectMembers, error: null });
    }
  }

  async function handleAddOrganizationMember(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token || !selectedOrganizationId) return;
    setBusyAction("add-organization-member");
    setBanner(null);
    try {
      await addOrganizationMember(session.data.token, selectedOrganizationId, {
        user_email: organizationMemberForm.email,
        role: organizationMemberForm.role,
      });
      setOrganizationMemberForm({ email: "", role: "Viewer" });
      await refreshMemberships();
      setBanner("Organization member added.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Organization member could not be added.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleOrganizationRoleChange(membershipId: string, role: string): Promise<void> {
    if (!session.data?.token || !selectedOrganizationId) return;
    setBusyAction(`organization-role-${membershipId}`);
    setBanner(null);
    try {
      await changeOrganizationMemberRole(
        session.data.token,
        selectedOrganizationId,
        membershipId,
        role,
      );
      await refreshMemberships();
      setBanner("Organization role updated.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Organization role could not be updated.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRemoveOrganizationMember(membership: OrganizationMembership): Promise<void> {
    if (!session.data?.token || !selectedOrganizationId) return;
    if (!window.confirm(`Remove ${membership.user?.display_name ?? "this user"} from the Organization?`)) return;
    setBusyAction(`remove-organization-${membership.id}`);
    setBanner(null);
    try {
      await removeOrganizationMember(session.data.token, selectedOrganizationId, membership.id);
      if (membership.user?.id === session.data.user.id) {
        setSelectedOrganizationId(null);
        setSelectedProjectId(null);
        const refreshedOrganizations = await listOrganizations(session.data.token);
        setOrganizations({ status: "ready", data: refreshedOrganizations, error: null });
      } else {
        await refreshMemberships();
      }
      setBanner("Organization member removed.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Organization member could not be removed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleAddProjectMember(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token || !selectedProjectId || !projectMemberForm.userId) return;
    setBusyAction("add-project-member");
    setBanner(null);
    try {
      await addProjectMember(session.data.token, selectedProjectId, {
        user_id: projectMemberForm.userId,
        role: projectMemberForm.role,
      });
      setProjectMemberForm({ userId: "", role: "Viewer" });
      await refreshMemberships();
      setBanner("Project member added.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Project member could not be added.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleProjectRoleChange(membershipId: string, role: string): Promise<void> {
    if (!session.data?.token || !selectedProjectId) return;
    setBusyAction(`project-role-${membershipId}`);
    setBanner(null);
    try {
      await changeProjectMemberRole(session.data.token, selectedProjectId, membershipId, role);
      await refreshMemberships();
      setBanner("Project role updated.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Project role could not be updated.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRemoveProjectMember(membership: ProjectMembership): Promise<void> {
    if (!session.data?.token || !selectedProjectId) return;
    if (!window.confirm(`Remove ${membership.user?.display_name ?? "this user"} from the Project?`)) return;
    setBusyAction(`remove-project-${membership.id}`);
    setBanner(null);
    try {
      await removeProjectMember(session.data.token, selectedProjectId, membership.id);
      if (membership.user?.id === session.data.user.id) {
        setSelectedProjectId(null);
        setProjectMembers(createLoadable([]));
      } else {
        await refreshMemberships();
      }
      setBanner("Project member removed.");
    } catch (error) {
      setBanner(error instanceof Error ? error.message : "Project member could not be removed.");
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

  async function refreshNotifications(token: string): Promise<void> {
    const refreshed = await listNotifications(token);
    setNotifications({ status: "ready", data: refreshed, error: null });
  }

  async function handleMarkNotificationRead(notificationId: string): Promise<void> {
    if (!session.data?.token) {
      return;
    }
    setBusyAction(`read-notification-${notificationId}`);
    setBanner(null);
    try {
      const updated = await markNotificationRead(session.data.token, notificationId);
      setNotifications((current) => ({
        status: "ready",
        error: null,
        data: current.data.map((item) => (item.id === updated.id ? updated : item)),
      }));
      setBanner("Notification marked as read.");
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Notification could not be updated.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRefreshNotifications(): Promise<void> {
    if (!session.data?.token) {
      return;
    }
    setBusyAction("refresh-notifications");
    setBanner(null);
    try {
      await refreshNotifications(session.data.token);
      setBanner("Notifications refreshed.");
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Notifications could not be refreshed.");
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
      await refreshNotifications(session.data.token);
      setAssetDetail({ status: "ready", data: nextAsset, error: null });
      setAssetHistory({ status: "ready", data: nextHistory, error: null });
      setCollaborationState({ status: "ready", data: nextCollaborationState, error: null });
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      const refreshed = await listAssets(session.data.token, selectedProjectId!);
      setAssets({ status: "ready", data: refreshed, error: null });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        await refreshNotifications(session.data.token);
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
      await refreshNotifications(session.data.token);
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      setBanner("Asset checked out for collaboration.");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        await refreshNotifications(session.data.token);
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
      await refreshNotifications(session.data.token);
      setAssetTimeline({ status: "ready", data: nextTimeline, error: null });
      setBanner(force ? "Asset force-unlocked." : "Asset unlocked.");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        await refreshNotifications(session.data.token);
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
      const [
        nextAsset,
        nextHistory,
        nextRelationships,
        nextIncomingRelationships,
        nextOutgoingRelationships,
        nextReferences,
        nextGraph,
        nextCollaborationState,
        nextTimeline,
        refreshedAssets,
      ] =
        await Promise.all([
          getAsset(session.data.token, selectedAssetId),
          getAssetHistory(session.data.token, selectedAssetId),
          listAssetRelationships(session.data.token, selectedAssetId),
          listIncomingAssetRelationships(session.data.token, selectedAssetId),
          listOutgoingAssetRelationships(session.data.token, selectedAssetId),
          listAssetReferences(session.data.token, selectedAssetId),
          getAssetGraph(session.data.token, selectedAssetId, { direction: "both", maxDepth: 3 }),
          getCollaborationState(session.data.token, selectedAssetId),
          getAssetTimeline(session.data.token, selectedAssetId),
          listAssets(session.data.token, selectedProjectId),
        ]);
      await refreshNotifications(session.data.token);
      setAssetDetail({ status: "ready", data: nextAsset, error: null });
      setAssetHistory({ status: "ready", data: nextHistory, error: null });
      setAssetRelationships({ status: "ready", data: nextRelationships, error: null });
      setIncomingRelationships({ status: "ready", data: nextIncomingRelationships, error: null });
      setOutgoingRelationships({ status: "ready", data: nextOutgoingRelationships, error: null });
      setAssetReferences({ status: "ready", data: nextReferences, error: null });
      setAssetGraph({ status: "ready", data: nextGraph, error: null });
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

  async function refreshPlugins(): Promise<void> {
    if (!session.data?.token || !session.data.user.is_platform_admin) return;
    const result = await listPlugins(session.data.token);
    setPlugins({ status: "ready", data: result, error: null });
  }

  async function handleApplyMetadataProvider(provider: ProviderDescriptor): Promise<void> {
    if (
      !session.data?.token ||
      !selectedAssetId ||
      !selectedProjectId ||
      !selectedOrganizationId
    ) return;
    setBusyAction(`provider-metadata-${provider.id}`);
    setBanner(null);
    try {
      const category = providerSelections[provider.id];
      await invokeMetadataProvider(session.data.token, provider.id, {
        target_type: "asset",
        target_id: selectedAssetId,
        project_id: selectedProjectId,
        organization_id: selectedOrganizationId,
        parameters: category ? { category } : {},
      });
      const metadata = await listMetadata(session.data.token, "asset", selectedAssetId);
      setAssetMetadata({ status: "ready", data: metadata, error: null });
      setBanner(`${provider.name} metadata applied.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Metadata Provider invocation failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleInstallPlugin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!session.data?.token || !pluginPackage) return;
    setBusyAction("install-plugin");
    setBanner(null);
    try {
      await installPluginPackage(session.data.token, pluginPackage);
      await refreshPlugins();
      setPluginPackage(null);
      setBanner("Community Plugin installed.");
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin installation failed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handlePluginState(plugin: PluginRecord): Promise<void> {
    if (!session.data?.token) return;
    setBusyAction(`plugin-state-${plugin.id}`);
    setBanner(null);
    try {
      await setPluginState(session.data.token, plugin.id, !plugin.enabled);
      await refreshPlugins();
      setBanner(`${plugin.name} ${plugin.enabled ? "disabled" : "enabled"}.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin state could not be updated.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleLoadPluginConfiguration(pluginId: string): Promise<void> {
    if (!session.data?.token) return;
    setBusyAction(`plugin-config-load-${pluginId}`);
    try {
      const configuration = await getPluginConfiguration(session.data.token, pluginId);
      setPluginConfiguration((current) => ({
        ...current,
        [pluginId]: JSON.stringify(configuration.values, null, 2),
      }));
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin configuration could not be loaded.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSavePluginConfiguration(pluginId: string): Promise<void> {
    if (!session.data?.token) return;
    setBusyAction(`plugin-config-save-${pluginId}`);
    setBanner(null);
    try {
      const values = JSON.parse(pluginConfiguration[pluginId] ?? "{}") as Record<string, unknown>;
      await updatePluginConfiguration(session.data.token, pluginId, values);
      await refreshPlugins();
      setBanner("Plugin configuration saved.");
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin configuration is not valid JSON.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRemovePlugin(plugin: PluginRecord): Promise<void> {
    if (!session.data?.token) return;
    if (!window.confirm(`Remove ${plugin.name}? Immutable package evidence will be retained.`)) return;
    setBusyAction(`plugin-remove-${plugin.id}`);
    setBanner(null);
    try {
      await removePlugin(session.data.token, plugin.id);
      await refreshPlugins();
      setBanner(`${plugin.name} removed.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin could not be removed.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUpgradePlugin(plugin: PluginRecord): Promise<void> {
    const packageFile = pluginUpgradePackages[plugin.id];
    if (!session.data?.token || !packageFile) return;
    setBusyAction(`plugin-upgrade-${plugin.id}`);
    setBanner(null);
    try {
      await upgradePluginPackage(session.data.token, plugin.id, packageFile);
      setPluginUpgradePackages((current) => ({ ...current, [plugin.id]: null }));
      await refreshPlugins();
      setBanner(`${plugin.name} upgraded and left disabled for review.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin upgrade failed.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <main className="app-shell">
      {isAuthenticated ? (
        <header className="app-topbar">
          <button
            aria-label="Open navigation"
            className="icon-button mobile-menu-button"
            onClick={() => setMobileNavigationOpen(true)}
            type="button"
          >
            <Menu />
          </button>
          <button className="brand" onClick={() => navigate("/")} type="button">
            <span className="brand-mark"><Boxes /></span>
            <span><strong>OpenPDM</strong><small>Engineering collaboration</small></span>
          </button>
          <div className="topbar-status">
            <span className="health-dot" />
            {foundation.data?.phase ?? "Connecting to API"}
          </div>
          <button className="icon-button" aria-label="Notifications" onClick={() => navigate("/")} type="button">
            <Bell />
            {unreadNotifications ? <span className="notification-count">{unreadNotifications}</span> : null}
          </button>
          <div className="user-avatar" title={session.data?.user.email}>
            {session.data?.user.display_name.slice(0, 2).toUpperCase()}
          </div>
          <button className="icon-button" aria-label="Sign out" onClick={() => void handleSignOut()} type="button">
            <LogOut />
          </button>
        </header>
      ) : (
        <section className="hero-panel auth-hero">
          <div>
            <p className="eyebrow">Engineering Collaboration Platform</p>
            <h1>OpenPDM</h1>
            <p className="intro">Organize, version, relate and secure engineering assets through one open platform.</p>
          </div>
          <dl className="foundation-grid">
            <div><dt>API Status</dt><dd>{foundation.data ? foundation.data.phase : foundation.error ?? "Loading..."}</dd></div>
            <div><dt>Architecture</dt><dd>{foundation.data?.architecture ?? "Connecting..."}</dd></div>
            <div><dt>Version</dt><dd>{foundation.data?.version ?? "Unknown"}</dd></div>
          </dl>
        </section>
      )}

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
          <section className="workspace-grid">
            {mobileNavigationOpen ? <button aria-label="Close navigation overlay" className="nav-scrim" onClick={() => setMobileNavigationOpen(false)} type="button" /> : null}
            <aside className={mobileNavigationOpen ? "nav-panel is-open" : "nav-panel"}>
              <header className="panel-header">
                <div>
                  <p className="eyebrow">Workspace</p>
                  <h2>Navigation</h2>
                </div>
                <button aria-label="Close navigation" className="icon-button close-nav-button" onClick={() => setMobileNavigationOpen(false)} type="button"><X /></button>
              </header>

              <button
                className={view === "home" ? "sidebar-link is-active" : "sidebar-link"}
                onClick={() => { setMobileNavigationOpen(false); navigate("/"); }}
                type="button"
              >
                <Home /> Home
              </button>

              <button className={view === "projects" ? "sidebar-link is-active" : "sidebar-link"} onClick={() => { setMobileNavigationOpen(false); navigate("/projects"); }} type="button"><FolderKanban /> Projects <span>{projects.data.length}</span></button>

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
                          onClick={() => {
                            setSelectedProjectId(project.id);
                            setMobileNavigationOpen(false);
                            navigate(`/projects/${project.id}/overview`);
                          }}
                          type="button"
                        >
                          <strong>{project.name}</strong>
                          <span>{project.description || "No description"}</span>
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {view === "project" && projectTab === "members" && selectedOrganizationId ? (
                    <section className="membership-panel" aria-labelledby="organization-members-heading">
                      <h3 id="organization-members-heading">Organization members</h3>
                      <p className="muted-text">
                        Owners control Owner roles. Every Organization must retain an Owner.
                      </p>
                      {organizationMembers.status === "error" ? (
                        <p className="error-message" role="alert">{organizationMembers.error}</p>
                      ) : null}
                      <div className="member-list">
                        {organizationMembers.data.map((membership) => {
                          const canManageTarget =
                            canManageOrganizationMembers &&
                            (membership.role !== "Owner" || currentOrganizationRole === "Owner");
                          return (
                            <div className="member-row" key={membership.id}>
                              <span>
                                <strong>{membership.user?.display_name ?? "Unknown user"}</strong>
                                <small>{membership.user?.email}</small>
                              </span>
                              <select
                                aria-label={`Organization role for ${membership.user?.display_name ?? "member"}`}
                                disabled={!canManageTarget || busyAction === `organization-role-${membership.id}`}
                                value={membership.role}
                                onChange={(event) => void handleOrganizationRoleChange(membership.id, event.target.value)}
                              >
                                {currentOrganizationRole === "Owner" || membership.role === "Owner" ? <option>Owner</option> : null}
                                <option>Maintainer</option>
                                <option>Contributor</option>
                                <option>Viewer</option>
                              </select>
                              {canManageTarget ? (
                                <button
                                  className="secondary-button"
                                  disabled={busyAction === `remove-organization-${membership.id}`}
                                  onClick={() => void handleRemoveOrganizationMember(membership)}
                                  type="button"
                                >
                                  Remove
                                </button>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                      {canManageOrganizationMembers ? (
                        <form className="form-grid compact-form" onSubmit={handleAddOrganizationMember}>
                          <h4>Add registered user</h4>
                          <label>
                            Email
                            <input
                              required
                              type="email"
                              value={organizationMemberForm.email}
                              onChange={(event) => setOrganizationMemberForm((current) => ({ ...current, email: event.target.value }))}
                            />
                          </label>
                          <label>
                            Organization role
                            <select
                              value={organizationMemberForm.role}
                              onChange={(event) => setOrganizationMemberForm((current) => ({ ...current, role: event.target.value }))}
                            >
                              {currentOrganizationRole === "Owner" ? <option>Owner</option> : null}
                              <option>Maintainer</option>
                              <option>Contributor</option>
                              <option>Viewer</option>
                            </select>
                          </label>
                          <button className="primary-button" disabled={busyAction === "add-organization-member"} type="submit">
                            {busyAction === "add-organization-member" ? "Adding..." : "Add member"}
                          </button>
                        </form>
                      ) : null}
                    </section>
                  ) : null}

                  {view === "project" && projectTab === "members" && selectedProjectId ? (
                    <section className="membership-panel" aria-labelledby="project-members-heading">
                      <h3 id="project-members-heading">Project members</h3>
                      <p className="muted-text">
                        Project members must already belong to the Organization.
                      </p>
                      {projectMembers.status === "error" ? (
                        <p className="error-message" role="alert">{projectMembers.error}</p>
                      ) : null}
                      <div className="member-list">
                        {projectMembers.data.map((membership) => {
                          const canManageTarget =
                            canManageProjectMembers &&
                            (membership.role !== "Owner" || currentProjectRole === "Owner");
                          return (
                            <div className="member-row" key={membership.id}>
                              <span>
                                <strong>{membership.user?.display_name ?? "Unknown user"}</strong>
                                <small>{membership.user?.email}</small>
                              </span>
                              <select
                                aria-label={`Project role for ${membership.user?.display_name ?? "member"}`}
                                disabled={!canManageTarget || busyAction === `project-role-${membership.id}`}
                                value={membership.role}
                                onChange={(event) => void handleProjectRoleChange(membership.id, event.target.value)}
                              >
                                {currentProjectRole === "Owner" || membership.role === "Owner" ? <option>Owner</option> : null}
                                <option>Maintainer</option>
                                <option>Contributor</option>
                                <option>Viewer</option>
                              </select>
                              {canManageTarget ? (
                                <button
                                  className="secondary-button"
                                  disabled={busyAction === `remove-project-${membership.id}`}
                                  onClick={() => void handleRemoveProjectMember(membership)}
                                  type="button"
                                >
                                  Remove
                                </button>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                      {canManageProjectMembers ? (
                        <form className="form-grid compact-form" onSubmit={handleAddProjectMember}>
                          <h4>Add Organization member</h4>
                          <label>
                            User
                            <select
                              required
                              value={projectMemberForm.userId}
                              onChange={(event) => setProjectMemberForm((current) => ({ ...current, userId: event.target.value }))}
                            >
                              <option value="">Select a user</option>
                              {organizationMembers.data
                                .filter((candidate) => candidate.user && !projectMembers.data.some((member) => member.user?.id === candidate.user?.id))
                                .map((candidate) => (
                                  <option key={candidate.id} value={candidate.user?.id}>
                                    {candidate.user?.display_name} ({candidate.user?.email})
                                  </option>
                                ))}
                            </select>
                          </label>
                          <label>
                            Project role
                            <select
                              value={projectMemberForm.role}
                              onChange={(event) => setProjectMemberForm((current) => ({ ...current, role: event.target.value }))}
                            >
                              {currentProjectRole === "Owner" ? <option>Owner</option> : null}
                              <option>Maintainer</option>
                              <option>Contributor</option>
                              <option>Viewer</option>
                            </select>
                          </label>
                          <button className="primary-button" disabled={busyAction === "add-project-member"} type="submit">
                            {busyAction === "add-project-member" ? "Adding..." : "Add to Project"}
                          </button>
                        </form>
                      ) : null}
                    </section>
                  ) : null}
                </>
              )}

              <div className="sidebar-footer">
                <button
                  className={
                    view === "plugin-administration"
                      ? "sidebar-link is-active"
                      : "sidebar-link"
                  }
                  onClick={() => { setMobileNavigationOpen(false); navigate("/administration/plugins"); }}
                  title={
                    session.data?.user.is_platform_admin
                      ? "Manage installed plugins"
                      : "Platform Administrator authority is required"
                  }
                  type="button"
                >
                  <Package /> Plugin administration
                </button>
              </div>
            </aside>

            {view === "home" || view === "projects" ? (
              <section className="panel home-panel content-span">
                <header className="panel-header">
                  <div>
                    <p className="eyebrow">{view === "home" ? "Home" : "Projects"}</p>
                    <h2>{view === "home" ? `Welcome, ${session.data?.user.display_name}` : "Available Projects"}</h2>
                    <p className="muted-text">
                      Choose a Project from the sidebar when you are ready to work with Engineering
                      Assets.
                    </p>
                  </div>
                  <span className="status-pill">
                    {unreadNotifications} unread
                  </span>
                </header>

                <div className="home-summary-grid">
                  <article className="detail-card">
                    <h3>Available Organizations</h3>
                    <p>{organizations.data.length} available to your account</p>
                    <ul className="home-list">
                      {organizations.data.map((membership) => (
                        <li key={membership.id}>
                          <strong>{membership.organization?.name}</strong>
                          <span>{membership.role}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                  <article className="detail-card">
                    <h3>Available Projects</h3>
                    <p>{projects.data.length} in the selected Organization</p>
                    <ul className="home-list">
                      {projects.data.map((project) => (
                        <li key={project.id}>
                          <button
                            className="text-button"
                            onClick={() => {
                              setSelectedProjectId(project.id);
                              navigate(`/projects/${project.id}/overview`);
                            }}
                            type="button"
                          >
                            {project.name}
                          </button>
                          <span>{project.description || "No description"}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                </div>

                {view === "home" ? <article className="detail-card notification-card">
                  <div className="detail-row">
                    <div>
                      <h3>Notifications</h3>
                      <p>Recent collaboration activity for your account.</p>
                    </div>
                    <button
                      className="secondary-button"
                      disabled={busyAction === "refresh-notifications"}
                      onClick={() => void handleRefreshNotifications()}
                      type="button"
                    >
                      Refresh
                    </button>
                  </div>
                  {notifications.data.length ? (
                    <div className="timeline">
                      {notifications.data.slice(0, 8).map((notification) => (
                        <article key={notification.id} className="timeline-card notification-item">
                          <div className="timeline-header">
                            <div>
                              <h3>{formatNotificationEvent(notification.event_type)}</h3>
                              <p>{notificationSummary(notification)}</p>
                            </div>
                            <small>{formatTimestamp(notification.created_at)}</small>
                          </div>
                          <span
                            className={
                              notification.is_read
                                ? "status-pill notification-pill notification-read"
                                : "status-pill notification-pill notification-unread"
                            }
                          >
                            {notification.is_read ? "read" : "unread"}
                          </span>
                          {!notification.is_read ? (
                            <button
                              className="secondary-button"
                              onClick={() => void handleMarkNotificationRead(notification.id)}
                              type="button"
                            >
                              Mark as read
                            </button>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-state">No notifications yet.</p>
                  )}
                </article> : null}
              </section>
            ) : null}

            {view === "plugin-administration" ? (
              <section className="panel admin-panel content-span">
                <header className="panel-header">
                  <div>
                    <p className="eyebrow">Platform Administration</p>
                    <h2>Plugin administration</h2>
                    <p className="muted-text">
                      Install, inspect, configure, enable and disable plugins through the public API.
                    </p>
                  </div>
                </header>
                {!session.data?.user.is_platform_admin ? (
                  <div className="empty-state access-denied">
                    <Package />
                    <h3>Platform Administrator authority required</h3>
                    <p>Organization and Project roles do not grant access to deployment-wide plugin administration.</p>
                  </div>
                ) : (
                  <>
                <form className="form-grid compact-form" onSubmit={handleInstallPlugin}>
                  <h3>Install Community Plugin</h3>
                  <label>
                    OpenPDM plugin package
                    <input
                      accept=".openpdm-plugin,application/zip"
                      required
                      type="file"
                      onChange={(event) => setPluginPackage(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <button
                    className="primary-button"
                    disabled={!pluginPackage || busyAction === "install-plugin"}
                    type="submit"
                  >
                    {busyAction === "install-plugin" ? "Installing..." : "Install package"}
                  </button>
                </form>
                {plugins.status === "error" ? (
                  <p className="error-message" role="alert">{plugins.error}</p>
                ) : null}
                <div className="plugin-grid">
                  {plugins.data.map((plugin) => (
                    <article className="detail-card plugin-card" key={plugin.id}>
                      <div className="detail-row">
                        <div>
                          <h3>{plugin.name}</h3>
                          <p>{plugin.id} · v{plugin.version}</p>
                        </div>
                        <span className="status-pill">{plugin.lifecycle_state}</span>
                      </div>
                      <p className="muted-text">{plugin.capabilities.join(", ")}</p>
                      {plugin.diagnostic_reason ? (
                        <p className="error-message">{plugin.diagnostic_reason}</p>
                      ) : null}
                      <div className="collaboration-actions">
                        <button
                          className="secondary-button"
                          disabled={busyAction === `plugin-state-${plugin.id}`}
                          onClick={() => void handlePluginState(plugin)}
                          type="button"
                        >
                          {plugin.enabled ? "Disable" : "Enable"}
                        </button>
                        <button
                          className="secondary-button"
                          onClick={() => void handleLoadPluginConfiguration(plugin.id)}
                          type="button"
                        >
                          Load configuration
                        </button>
                        <button
                          className="secondary-button warning-button"
                          disabled={plugin.enabled || busyAction === `plugin-remove-${plugin.id}`}
                          onClick={() => void handleRemovePlugin(plugin)}
                          type="button"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="plugin-upgrade-row">
                        <label>
                          Same-identity upgrade package
                          <input
                            accept=".openpdm-plugin,application/zip"
                            disabled={plugin.enabled}
                            type="file"
                            onChange={(event) =>
                              setPluginUpgradePackages((current) => ({
                                ...current,
                                [plugin.id]: event.target.files?.[0] ?? null,
                              }))
                            }
                          />
                        </label>
                        <button
                          className="secondary-button"
                          disabled={
                            plugin.enabled ||
                            !pluginUpgradePackages[plugin.id] ||
                            busyAction === `plugin-upgrade-${plugin.id}`
                          }
                          onClick={() => void handleUpgradePlugin(plugin)}
                          type="button"
                        >
                          {busyAction === `plugin-upgrade-${plugin.id}` ? "Upgrading..." : "Upgrade"}
                        </button>
                      </div>
                      {pluginConfiguration[plugin.id] !== undefined ? (
                        <div className="form-grid plugin-configuration">
                          <label>
                            Configuration values (JSON)
                            <textarea
                              value={pluginConfiguration[plugin.id]}
                              onChange={(event) =>
                                setPluginConfiguration((current) => ({
                                  ...current,
                                  [plugin.id]: event.target.value,
                                }))
                              }
                            />
                          </label>
                          <button
                            className="primary-button"
                            onClick={() => void handleSavePluginConfiguration(plugin.id)}
                            type="button"
                          >
                            Save configuration
                          </button>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
                  </>
                )}
              </section>
            ) : null}

            {view === "project" ? (
              <>
                <section className="panel project-header content-span">
                  <div className="project-heading-row">
                    <div>
                      <p className="breadcrumb">
                        Projects <ChevronRight size={14} /> {projects.data.find((item) => item.id === selectedProjectId)?.name ?? "Project"}
                      </p>
                      <h2>{projects.data.find((item) => item.id === selectedProjectId)?.name ?? "Project workspace"}</h2>
                      <p className="muted-text">
                        {projects.data.find((item) => item.id === selectedProjectId)?.description || "Engineering collaboration workspace"}
                      </p>
                    </div>
                    <span className="status-pill">{currentProjectRole ?? "Member"}</span>
                  </div>
                  <nav className="project-tabs" aria-label="Project sections">
                    {([
                      ["overview", "Overview"],
                      ["assets", "Assets"],
                      ["relationships", "Relationships"],
                      ["collaboration", "Collaboration"],
                      ["members", "Members"],
                    ] as Array<[ProjectTab, string]>).map(([tab, label]) => (
                      <button
                        className={projectTab === tab ? "project-tab is-active" : "project-tab"}
                        key={tab}
                        onClick={() => navigate(`/projects/${selectedProjectId}/${tab}`)}
                        type="button"
                      >
                        {label}
                      </button>
                    ))}
                  </nav>
                </section>

                {projectTab === "overview" ? (
                  <section className="panel content-span project-overview">
                    <div className="metric-grid">
                      <article className="metric-card"><span>Assets</span><strong>{assets.data.length}</strong><small>Versioned Engineering Assets</small></article>
                      <article className="metric-card"><span>Collaborators</span><strong>{projectMembers.data.length}</strong><small>Project members</small></article>
                      <article className="metric-card"><span>Unread</span><strong>{notifications.data.filter((item) => !item.is_read && item.project_id === selectedProjectId).length}</strong><small>Project notifications</small></article>
                      <article className="metric-card"><span>Your role</span><strong>{currentProjectRole ?? "Member"}</strong><small>Current Project authority</small></article>
                    </div>
                    <div className="overview-grid">
                      <article className="detail-card">
                        <h3>Recent Assets</h3>
                        <div className="compact-list">
                          {assets.data.slice(0, 6).map((asset) => (
                            <button key={asset.id} onClick={() => { setSelectedAssetId(asset.id); navigate(`/projects/${selectedProjectId}/assets`); }} type="button">
                              <span>{asset.name}</span><small>{asset.status}</small>
                            </button>
                          ))}
                        </div>
                      </article>
                      <article className="detail-card">
                        <h3>Collaboration feed</h3>
                        <div className="compact-list">
                          {notifications.data.filter((item) => item.project_id === selectedProjectId).slice(0, 6).map((item) => (
                            <div key={item.id}><span>{formatNotificationEvent(item.event_type)}</span><small>{formatTimestamp(item.created_at)}</small></div>
                          ))}
                        </div>
                      </article>
                    </div>
                  </section>
                ) : null}

                {projectTab === "relationships" ? (
                  <section className="panel content-span focused-panel">
                    <header className="panel-header"><div><p className="eyebrow">Asset Graph</p><h2>Relationships</h2></div><Network /></header>
                    <p className="muted-text">Select an Asset in the Assets tab to inspect its bounded graph and references.</p>
                    {assetDetail.data ? (
                      <div className="overview-grid">
                        <article className="detail-card"><h3>{assetDetail.data.name}</h3><p>{assetRelationships.data.length} relationships · {assetReferences.data.length} references</p><div className="compact-list">{assetRelationships.data.map((item) => <div key={item.id}><span>{formatRelationshipType(item.relationship_type)}</span><small>{assetNameById.get(item.target_asset_id) ?? item.target_asset_id}</small></div>)}</div></article>
                        <article className="detail-card"><h3>Bounded graph</h3><p>{assetGraph.data?.nodes.length ?? 0} nodes · {assetGraph.data?.relationships.length ?? 0} links</p><div className="graph-node-list">{assetGraph.data?.nodes.map((node) => <span key={node.id}>{node.name}</span>)}</div></article>
                      </div>
                    ) : <p className="empty-state">No Asset selected.</p>}
                  </section>
                ) : null}

                {projectTab === "collaboration" ? (
                  <section className="panel content-span focused-panel">
                    <header className="panel-header"><div><p className="eyebrow">Live context</p><h2>Collaboration</h2></div><Activity /></header>
                    <div className="overview-grid">
                      <article className="detail-card"><h3>Selected Asset state</h3><p>{assetDetail.data?.name ?? "No Asset selected"}</p><span className="status-pill">{collaborationState.data?.state ?? "unavailable"}</span></article>
                      <article className="detail-card"><h3>Project notifications</h3><div className="compact-list">{notifications.data.filter((item) => item.project_id === selectedProjectId).slice(0, 8).map((item) => <div key={item.id}><span>{formatNotificationEvent(item.event_type)}</span><small>{formatTimestamp(item.created_at)}</small></div>)}</div></article>
                    </div>
                  </section>
                ) : null}

                {projectTab === "members" ? (
                  <section className="panel content-span focused-panel">
                    <header className="panel-header"><div><p className="eyebrow">Access</p><h2>Project members</h2></div><Users /></header>
                    <p className="muted-text">Membership controls are available in the sidebar for the selected Organization and Project.</p>
                  </section>
                ) : null}

                {projectTab === "assets" ? (
                  <>
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

              <article className="detail-card notification-card">
                <div className="detail-row">
                  <div>
                    <h3>Collaboration notifications</h3>
                    <p>
                      {unreadNotifications > 0
                        ? `${unreadNotifications} unread notification${unreadNotifications === 1 ? "" : "s"}`
                        : "No unread notifications"}
                    </p>
                  </div>
                  <button
                    className="secondary-button"
                    disabled={busyAction === "refresh-notifications"}
                    onClick={() => void handleRefreshNotifications()}
                    type="button"
                  >
                    {busyAction === "refresh-notifications" ? "Refreshing..." : "Refresh"}
                  </button>
                </div>

                {notifications.status === "error" ? (
                  <p className="error-message" role="alert">
                    {notifications.error}
                  </p>
                ) : null}

                {notifications.data.length > 0 ? (
                  <div className="timeline">
                    {notifications.data.map((notification) => (
                      <article key={notification.id} className="timeline-card notification-item">
                        <div className="timeline-header">
                          <div>
                            <h3>{formatNotificationEvent(notification.event_type)}</h3>
                            <p>{notificationSummary(notification)}</p>
                          </div>
                          <small>{formatTimestamp(notification.created_at)}</small>
                        </div>
                        <div className="notification-meta">
                          <span
                            className={
                              notification.is_read
                                ? "status-pill notification-pill notification-read"
                                : "status-pill notification-pill notification-unread"
                            }
                          >
                            {notification.is_read ? "read" : "unread"}
                          </span>
                          {!notification.is_read ? (
                            <button
                              className="secondary-button"
                              disabled={busyAction === `read-notification-${notification.id}`}
                              onClick={() => void handleMarkNotificationRead(notification.id)}
                              type="button"
                            >
                              {busyAction === `read-notification-${notification.id}`
                                ? "Marking..."
                                : "Mark as read"}
                            </button>
                          ) : null}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty-state">
                    Collaboration notifications will appear here when approved Phase 2 events target
                    your account.
                  </p>
                )}
              </article>

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

                  <article className="detail-card provider-card">
                    <div className="detail-row">
                      <div>
                        <h3>Plugin-provided metadata</h3>
                        <p>Apply capabilities discovered through the public provider API.</p>
                      </div>
                      <span className="status-pill">{assetMetadata.data.length} entries</span>
                    </div>

                    {providers.data.filter((provider) =>
                      provider.capabilities.includes("metadata_provider"),
                    ).map((provider) => {
                      const optionSet = providerOptions[provider.id]?.find(
                        (item) => item.key === "category",
                      );
                      return (
                        <div className="provider-control" key={provider.id}>
                          <div>
                            <strong>{provider.name}</strong>
                            <small>{provider.id}</small>
                          </div>
                          {optionSet ? (
                            <label>
                              {optionSet.label}
                              <select
                                value={providerSelections[provider.id] ?? optionSet.options[0]?.value ?? ""}
                                onChange={(event) =>
                                  setProviderSelections((current) => ({
                                    ...current,
                                    [provider.id]: event.target.value,
                                  }))
                                }
                              >
                                {optionSet.options.map((option) => (
                                  <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                              </select>
                            </label>
                          ) : null}
                          <button
                            className="secondary-button"
                            disabled={busyAction === `provider-metadata-${provider.id}`}
                            onClick={() => void handleApplyMetadataProvider(provider)}
                            type="button"
                          >
                            {busyAction === `provider-metadata-${provider.id}` ? "Applying..." : "Apply metadata"}
                          </button>
                        </div>
                      );
                    })}

                    {providers.data.every((provider) =>
                      !provider.capabilities.includes("metadata_provider"),
                    ) ? (
                      <p className={providers.status === "error" ? "error-message" : "empty-state"}>
                        {providers.status === "error"
                          ? providers.error
                          : "No running Metadata Provider is available."}
                      </p>
                    ) : null}

                    {assetMetadata.data.length > 0 ? (
                      <dl className="metadata-list">
                        {assetMetadata.data.map((entry) => (
                          <div key={entry.id}>
                            <dt>{entry.key}</dt>
                            <dd>{typeof entry.value === "string" ? entry.value : JSON.stringify(entry.value)}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
                  </article>

                  <article className="detail-card relationship-card">
                    <div className="detail-row">
                      <div>
                        <h3>Asset relationships</h3>
                        <p>
                          Explore explicit Asset-to-Asset links without adding engineering-domain
                          semantics.
                        </p>
                      </div>
                      <span className="status-pill">
                        {assetRelationships.data.length} link
                        {assetRelationships.data.length === 1 ? "" : "s"}
                      </span>
                    </div>

                    {assetRelationships.status === "error" ||
                    incomingRelationships.status === "error" ||
                    outgoingRelationships.status === "error" ? (
                      <p className="error-message" role="alert">
                        {assetRelationships.error ??
                          incomingRelationships.error ??
                          outgoingRelationships.error}
                      </p>
                    ) : null}

                    <div className="relationship-grid">
                      <section className="relationship-column">
                        <div className="relationship-column-header">
                          <h4>Incoming</h4>
                          <span>{incomingRelationships.data.length}</span>
                        </div>
                        {incomingRelationships.data.length > 0 ? (
                          <div className="relationship-list">
                            {incomingRelationships.data.map((relationship) => (
                              <article key={relationship.id} className="relationship-item">
                                <div>
                                  <strong>{formatRelationshipType(relationship.relationship_type)}</strong>
                                  <p>
                                    From{" "}
                                    {assetNameById.get(relationship.source_asset_id) ??
                                      relationship.source_asset_id}
                                  </p>
                                  <small>{formatTimestamp(relationship.created_at)}</small>
                                  {formatMetadataSummary(relationship.metadata) ? (
                                    <small>{formatMetadataSummary(relationship.metadata)}</small>
                                  ) : null}
                                </div>
                                <button
                                  className="secondary-button"
                                  onClick={() => setSelectedAssetId(relationship.source_asset_id)}
                                  type="button"
                                >
                                  Open asset
                                </button>
                              </article>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-state">No Assets currently point to this Asset.</p>
                        )}
                      </section>

                      <section className="relationship-column">
                        <div className="relationship-column-header">
                          <h4>Outgoing</h4>
                          <span>{outgoingRelationships.data.length}</span>
                        </div>
                        {outgoingRelationships.data.length > 0 ? (
                          <div className="relationship-list">
                            {outgoingRelationships.data.map((relationship) => (
                              <article key={relationship.id} className="relationship-item">
                                <div>
                                  <strong>{formatRelationshipType(relationship.relationship_type)}</strong>
                                  <p>
                                    To{" "}
                                    {assetNameById.get(relationship.target_asset_id) ??
                                      relationship.target_asset_id}
                                  </p>
                                  <small>{formatTimestamp(relationship.created_at)}</small>
                                  {formatMetadataSummary(relationship.metadata) ? (
                                    <small>{formatMetadataSummary(relationship.metadata)}</small>
                                  ) : null}
                                </div>
                                <button
                                  className="secondary-button"
                                  onClick={() => setSelectedAssetId(relationship.target_asset_id)}
                                  type="button"
                                >
                                  Open asset
                                </button>
                              </article>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-state">This Asset has no outgoing relationships yet.</p>
                        )}
                      </section>
                    </div>
                  </article>

                  <article className="detail-card relationship-card">
                    <div className="detail-row">
                      <div>
                        <h3>Generic references</h3>
                        <p>
                          References stay distinct from graph edges so unresolved or external pointers
                          do not appear as Assets.
                        </p>
                      </div>
                      <span className="status-pill">
                        {assetReferences.data.length} reference
                        {assetReferences.data.length === 1 ? "" : "s"}
                      </span>
                    </div>

                    {assetReferences.status === "error" ? (
                      <p className="error-message" role="alert">
                        {assetReferences.error}
                      </p>
                    ) : null}

                    {assetReferences.data.length > 0 ? (
                      <div className="reference-list">
                        {assetReferences.data.map((reference) => (
                          <article key={reference.id} className="relationship-item reference-item">
                            <div>
                              <strong>{reference.label || reference.reference_type}</strong>
                              <p>{reference.target_uri}</p>
                              <small>{reference.reference_type}</small>
                              {formatMetadataSummary(reference.metadata) ? (
                                <small>{formatMetadataSummary(reference.metadata)}</small>
                              ) : null}
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-state">
                        No generic references are attached to this Asset yet.
                      </p>
                    )}
                  </article>

                  <article className="detail-card relationship-card">
                    <div className="detail-row">
                      <div>
                        <h3>Bounded graph summary</h3>
                        <p>
                          The Web UI uses the approved Phase 3 bounded graph read with direction{" "}
                          <code>both</code> and depth <code>3</code>.
                        </p>
                      </div>
                      <span className="status-pill">
                        {assetGraph.data?.has_cycle ? "cycle detected" : "no cycle"}
                      </span>
                    </div>

                    {assetGraph.status === "error" ? (
                      <p className="error-message" role="alert">
                        {assetGraph.error}
                      </p>
                    ) : null}

                    {assetGraph.data ? (
                      <div className="graph-summary-grid">
                        <article className="graph-summary-card">
                          <strong>Nodes</strong>
                          <span>{assetGraph.data.nodes.length}</span>
                        </article>
                        <article className="graph-summary-card">
                          <strong>Relationships</strong>
                          <span>{assetGraph.data.relationships.length}</span>
                        </article>
                        <article className="graph-summary-card">
                          <strong>Direction</strong>
                          <span>{assetGraph.data.direction}</span>
                        </article>
                        <article className="graph-summary-card">
                          <strong>Max depth</strong>
                          <span>{assetGraph.data.max_depth}</span>
                        </article>
                        <article className="graph-summary-card">
                          <strong>Path target</strong>
                          <span>{assetGraph.data.target_asset_id ?? "Not requested"}</span>
                        </article>
                        <article className="graph-summary-card">
                          <strong>Path exists</strong>
                          <span>
                            {assetGraph.data.path_exists === null
                              ? "Not evaluated"
                              : assetGraph.data.path_exists
                                ? "Yes"
                                : "No"}
                          </span>
                        </article>
                      </div>
                    ) : (
                      <p className="empty-state">Graph summary is loading for this Asset.</p>
                    )}
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
                  </>
                ) : null}
              </>
            ) : null}
          </section>
        </>
      )}
    </main>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <OpenPdmApp />
    </BrowserRouter>
  );
}

export default App;
