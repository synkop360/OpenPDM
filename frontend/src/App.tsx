import { startTransition, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Bell,
  Boxes,
  ChevronRight,
  FolderKanban,
  Inbox,
  Home,
  LogOut,
  Menu,
  Network,
  RefreshCw,
  Save,
  Search,
  Package,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { BrowserRouter, useLocation, useNavigate } from "react-router-dom";
import {
  ApiError,
  addOrganizationMember,
  addProjectMember,
  type AnalysisResult,
  type AssetGraph,
  type GraphNode,
  checkinAsset,
  checkoutAsset,
  addRepresentation,
  createAsset,
  createOrganization,
  createProject,
  createProjectAssetView,
  createRevision,
  changeOrganizationMemberRole,
  changeProjectMemberRole,
  deleteProjectAssetView,
  downloadBlob,
  discoverProviders,
  getAsset,
  getAssetGraph,
  getAssetHistory,
  getAssetTimeline,
  getCollaborationState,
  getCurrentSession,
  getPluginConfiguration,
  getProviderOptions,
  installPluginPackage,
  invokeAnalysisProvider,
  listAssetReferences,
  listAssetRelationships,
  listAssetsPage,
  listIncomingAssetRelationships,
  listMetadata,
  listNotificationsPage,
  listOrganizationProjects,
  listOrganizationMembers,
  listOutgoingAssetRelationships,
  listPlugins,
  listOrganizations,
  listProjectsForUser,
  listProjectMembers,
  listProjectAssetViews,
  markNotificationRead,
  markNotificationsRead,
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
  cancelBlobUploadSession,
  type Asset,
  type BlobRecord,
  type CollaborationState,
  type NotificationRecord,
  type OrganizationMembership,
  type Project,
  type ProjectAssetView,
  type ProjectMembership,
  type PluginRecord,
  type PluginConfiguration,
  type ProviderDescriptor,
  type ProviderOptionSet,
  type MetadataEntry,
  type Revision,
  type SessionInfo,
  type TimelineEntry,
  updatePluginConfiguration,
  upgradePluginPackage,
} from "./api";
import {
  collaborationGuidance,
  collaborationRecoveryAction,
  collaborationRequestId,
  collaborationShouldRefresh,
} from "./app/collaborationErrors";
import {
  formatNotificationEvent,
  formatRelationshipType,
  formatTimestamp,
  notificationSummary,
} from "./app/format";
import { createLoadable, type Loadable } from "./app/loadable";
import { parseAppRoute, projectAssetPath, type ProjectTab } from "./app/routes";
import {
  ASSET_KEY,
  ORG_KEY,
  PROJECT_KEY,
  SESSION_TOKEN_KEY,
  readStoredValue,
  writeStoredValue,
} from "./app/storage";
import { useRouteFocus } from "./app/useRouteFocus";
import { InlineAlert } from "./components/feedback/InlineAlert";
import { ProjectTabs } from "./components/navigation/ProjectTabs";
import { ConfirmDialog } from "./components/primitives/Dialog";
import { AppShell } from "./components/shell/AppShell";
import { AuthenticatedHeader } from "./components/shell/AuthenticatedHeader";
import { GuestHeader } from "./components/shell/GuestHeader";
import { AssetDetailPanel } from "./features/assets/AssetDetailPanel";
import { AssetGraphDiagram } from "./features/assets/AssetGraphDiagram";
import { useFoundationStatus } from "./hooks/useFoundationStatus";
import { type TransferPhase } from "./features/transfers/TransferStatus";
import {
  clearTransferRecovery,
  canReuseCompletedBlob,
  loadTransferRecovery,
  resumableUpload,
  type TransferRecovery,
} from "./features/transfers/resumableUpload";
import "./styles.css";

type AuthMode = "sign-in" | "register";

type ConfigurationProperty = {
  type?: string;
  title?: string;
  description?: string;
  enum?: unknown[];
  secret?: boolean;
};

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
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

const ROLE_IMPACT: Record<string, string> = {
  Owner: "Full administration, including Owner role changes and destructive governance actions.",
  Maintainer: "Can manage members and collaboration recovery, but cannot govern Owners.",
  Contributor: "Can create and update Engineering Assets without managing access.",
  Viewer: "Read-only access to the workspace.",
};

function configurationProperties(configuration: PluginConfiguration): Record<string, ConfigurationProperty> {
  const properties = configuration.configuration_schema?.properties;
  return properties && typeof properties === "object" && !Array.isArray(properties)
    ? properties as Record<string, ConfigurationProperty>
    : {};
}

function supportsSchemaForm(configuration: PluginConfiguration): boolean {
  const schema = configuration.configuration_schema;
  if (!schema || schema.type !== "object") return false;
  return Object.values(configurationProperties(configuration)).every((property) =>
    property.enum?.length || ["string", "number", "integer", "boolean"].includes(property.type ?? ""),
  );
}

function lockAge(createdAt: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"}`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hour${hours === 1 ? "" : "s"}`;
}

// Tabs whose content depends on which Engineering Asset is selected (the Assets tab's
// detail sheet, and the Relationships tab's own asset picker plus incoming/outgoing/
// references cards). Overview, Collaboration and Members show no asset-specific content,
// so selectedAssetId is neither restored, defaulted, nor cleared there -- an empty route on
// those tabs says nothing about asset selection either way.
const ASSET_AWARE_PROJECT_TABS: ReadonlySet<ProjectTab> = new Set(["assets", "relationships"]);

function OpenPdmApp() {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    projectId: routeProjectId,
    projectTab,
    view,
    assetId: routeAssetId,
  } = parseAppRoute(location.pathname);
  const assetSearchParams = new URLSearchParams(location.search);
  const assetFilterQuery = assetSearchParams.get("q") ?? "";
  const assetStatusFilter = assetSearchParams.get("status") ?? "";
  const assetSort = assetSearchParams.get("sort") ?? "updated_at";
  const assetDirection = assetSearchParams.get("direction") === "asc" ? "asc" : "desc";
  useRouteFocus();
  const foundation = useFoundationStatus();
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
  const [assetNextCursor, setAssetNextCursor] = useState<string | null>(null);
  const [assetCursor, setAssetCursor] = useState<string | null>(null);
  const [assetCursorHistory, setAssetCursorHistory] = useState<string[]>([]);
  const [assetReloadKey, setAssetReloadKey] = useState(0);
  const [assetViews, setAssetViews] = useState<Loadable<ProjectAssetView[]>>(
    createLoadable<ProjectAssetView[]>([]),
  );
  const [assetViewName, setAssetViewName] = useState("");
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
  const [projectGraph, setProjectGraph] = useState<Loadable<AssetGraph | null>>(
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
  const [notificationNextCursor, setNotificationNextCursor] = useState<string | null>(null);
  const [notificationCursor, setNotificationCursor] = useState<string | null>(null);
  const [notificationCursorHistory, setNotificationCursorHistory] = useState<string[]>([]);
  const [notificationFilter, setNotificationFilter] = useState<"all" | "unread">("unread");
  const [notificationProjectFilter, setNotificationProjectFilter] = useState("");
  const [selectedNotificationIds, setSelectedNotificationIds] = useState<string[]>([]);
  const [plugins, setPlugins] = useState<Loadable<PluginRecord[]>>(createLoadable<PluginRecord[]>([]));
  const [providers, setProviders] = useState<Loadable<ProviderDescriptor[]>>(
    createLoadable<ProviderDescriptor[]>([]),
  );
  const [providerOptions, setProviderOptions] = useState<Record<string, ProviderOptionSet[]>>({});
  const [providerSelections, setProviderSelections] = useState<Record<string, string>>({});
  const [analysisRepresentationId, setAnalysisRepresentationId] = useState("");
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [assetMetadata, setAssetMetadata] = useState<Loadable<MetadataEntry[]>>(
    createLoadable<MetadataEntry[]>([]),
  );
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [pluginPackage, setPluginPackage] = useState<File | null>(null);
  const [pluginConfigurations, setPluginConfigurations] = useState<Record<string, PluginConfiguration>>({});
  const [pluginConfigurationDrafts, setPluginConfigurationDrafts] = useState<Record<string, Record<string, unknown>>>({});
  const [pluginConfigurationJson, setPluginConfigurationJson] = useState<Record<string, string>>({});
  const [pluginConfigurationErrors, setPluginConfigurationErrors] = useState<Record<string, string | null>>({});
  const [pluginQuery, setPluginQuery] = useState("");
  const [pluginLifecycleFilter, setPluginLifecycleFilter] = useState("all");
  const [memberQuery, setMemberQuery] = useState("");
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
  const analysisRepresentations = assetHistory.data.flatMap((revision) =>
    revision.representations.map((representation) => ({ representation, revision })),
  );
  const selectedAnalysisRepresentation = analysisRepresentations.find(
    (item) => item.representation.id === analysisRepresentationId,
  )?.representation ?? analysisRepresentations[0]?.representation ?? null;
  const [transfer, setTransfer] = useState<{
    phase: TransferPhase;
    receivedBytes: number;
    totalBytes: number;
    message: string | null;
    blob: BlobRecord | null;
    assetId: string | null;
    recovery: TransferRecovery | null;
  }>({ phase: "idle", receivedBytes: 0, totalBytes: 0, message: null, blob: null,
    assetId: null, recovery: null });
  const transferOperation = useRef(0);
  const activeTransferOperation = useRef<{ id: number; controller: AbortController } | null>(null);
  const analysisOperation = useRef(0);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(
    readStoredValue(ORG_KEY),
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(readStoredValue(PROJECT_KEY));
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(readStoredValue(ASSET_KEY));

  useEffect(() => {
    transferOperation.current += 1;
    activeTransferOperation.current?.controller.abort();
    activeTransferOperation.current = null;
    setBusyAction((current) => current === "upload" ? null : current);
    setUploadForm((current) => ({ ...current, file: null, representationName: "" }));
    const userId = session.data?.user.id;
    if (!selectedAssetId || !userId) {
      setTransfer({ phase: "idle", receivedBytes: 0, totalBytes: 0, message: null,
        blob: null, assetId: null, recovery: null });
      return;
    }
    const recovery = loadTransferRecovery(userId, selectedAssetId);
    setTransfer({ phase: recovery ? "awaiting-file" : "idle", receivedBytes: 0,
      totalBytes: recovery?.fileSize ?? 0,
      message: recovery ? `Select ${recovery.fileName} to resume the interrupted transfer.` : null,
      blob: null, assetId: selectedAssetId, recovery });
  }, [selectedAssetId, session.data?.token]);

  useEffect(() => {
    if (routeProjectId && routeProjectId !== selectedProjectId) {
      setSelectedProjectId(routeProjectId);
    }
  }, [routeProjectId, selectedProjectId]);

  // Tracks an assetId this component itself just navigated to, so the sync effect below
  // does not revert setSelectedAssetId(...) when it reads a `routeAssetId` from a render
  // where `useLocation()` has not yet caught up with a `navigate()` issued in the same
  // event handler. Cleared once the route confirms the pending value. `undefined` means
  // "no pending self-initiated navigation" -- defer to the plain route-vs-state comparison.
  const pendingAssetNavigation = useRef<string | null | undefined>(undefined);
  // Whether the one-time localStorage-into-URL restore below has already been attempted.
  // Seeded from whether the page's very first URL already named an asset: if it did, the
  // user arrived with explicit context and the restore has nothing to contribute, so it's
  // pre-marked "attempted" -- otherwise it would fire on the *next* time the route happens
  // to have no asset (e.g. the user closing that very asset, or switching tabs right after),
  // silently overriding a deliberate action with a stale localStorage value.
  const assetRestoreAttempted = useRef(Boolean(routeAssetId));
  // The asset id localStorage held at mount, captured once before any effect (e.g. the one
  // that clears selectedAssetId when the Project changes, which also persists that clear
  // back to localStorage) can overwrite it. The restore below reads this snapshot, not a
  // fresh localStorage read, so it isn't racing its own persistence effect.
  const initialStoredAssetId = useRef(selectedAssetId);
  // Whether the most recent explicit selectAsset(...) call was a clear (assetId === null),
  // e.g. the user closing the detail panel. The auto-default effect below checks this so it
  // doesn't immediately re-select an Asset the user just deliberately deselected; reset
  // whenever a real Asset is chosen or the Project changes, so a fresh context can default
  // again.
  const assetExplicitlyCleared = useRef(false);

  const selectAsset = useCallback(
    (assetId: string | null, options?: { tab?: ProjectTab; replace?: boolean }) => {
      assetExplicitlyCleared.current = assetId === null;
      pendingAssetNavigation.current = assetId;
      setSelectedAssetId(assetId);
      if (selectedProjectId) {
        navigate(projectAssetPath(selectedProjectId, options?.tab ?? projectTab, assetId), {
          replace: options?.replace,
        });
      }
    },
    [navigate, projectTab, selectedProjectId],
  );

  useEffect(() => {
    if (pendingAssetNavigation.current !== undefined) {
      if (routeAssetId === pendingAssetNavigation.current) {
        pendingAssetNavigation.current = undefined;
      }
      return;
    }
    if (routeAssetId) {
      if (routeAssetId !== selectedAssetId) {
        setSelectedAssetId(routeAssetId);
      }
      return;
    }
    if (!selectedProjectId) {
      // No Project context yet (e.g. still on Home, or Organizations/Projects still
      // loading). Leave selectedAssetId as-is -- there is no route to reconcile against.
      return;
    }
    // The URL has no asset segment. Give the last-viewed asset remembered in localStorage
    // one chance to populate a selection (ADR-0050's fallback) -- on any Project tab, since
    // tabs like Collaboration display state for "whichever Asset is current" without
    // addressing one via their own URL. Only asset-aware tabs reflect the restored value in
    // the URL, matching ProjectTabs' own carry-over rule; elsewhere it's a plain default.
    if (!assetRestoreAttempted.current) {
      assetRestoreAttempted.current = true;
      const stored = initialStoredAssetId.current;
      if (stored) {
        if (ASSET_AWARE_PROJECT_TABS.has(projectTab)) {
          selectAsset(stored, { tab: projectTab, replace: true });
        } else {
          setSelectedAssetId(stored);
        }
        return;
      }
    }
    // Only an asset-aware tab's empty route is authoritative over an existing selection --
    // that's the only place a missing segment unambiguously means "no Asset chosen" (e.g.
    // after closing the detail panel, or navigating back to such a history entry). On other
    // tabs, an empty route says nothing about asset selection either way.
    if (ASSET_AWARE_PROJECT_TABS.has(projectTab) && selectedAssetId !== null) {
      setSelectedAssetId(null);
    }
  }, [routeAssetId, selectedAssetId, selectAsset, selectedProjectId, projectTab]);

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
  }, [projectTab, selectedOrganizationId, session.data?.token, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedProjectId || view !== "project" || projectTab !== "members") {
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
  }, [projectTab, selectedProjectId, session.data?.token, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedProjectId || view !== "project" || projectTab !== "relationships") {
      setProjectGraph(createLoadable(null));
      return;
    }
    if (assets.data.length === 0) {
      setProjectGraph({ status: "ready", data: null, error: null });
      return;
    }
    let cancelled = false;
    setProjectGraph((current) => ({ ...current, status: "loading", error: null }));
    Promise.all(
      assets.data.map((asset) => getAssetGraph(token, asset.id, { direction: "both", maxDepth: 10 })),
    )
      .then((graphs) => {
        if (cancelled) {
          return;
        }
        const nodesById = new Map<string, GraphNode>();
        const relationshipsById = new Map<string, Relationship>();
        let hasCycle = false;
        for (const graph of graphs) {
          for (const node of graph.nodes) {
            nodesById.set(node.id, node);
          }
          for (const relationship of graph.relationships) {
            relationshipsById.set(relationship.id, relationship);
          }
          hasCycle = hasCycle || graph.has_cycle;
        }
        setProjectGraph({
          status: "ready",
          data: {
            asset_id: assets.data[0]?.id ?? "",
            direction: "both",
            max_depth: 10,
            target_asset_id: null,
            path_exists: null,
            has_cycle: hasCycle,
            nodes: Array.from(nodesById.values()),
            relationships: Array.from(relationshipsById.values()),
          },
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setProjectGraph({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Project graph could not be loaded.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [assets.data, projectTab, selectedProjectId, session.data?.token, view]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token) {
      setNotifications(createLoadable([]));
      setNotificationNextCursor(null);
      return;
    }
    setNotifications((current) => ({ ...current, status: "loading", error: null }));
    listNotificationsPage(token, {
      limit: 50,
      cursor: notificationCursor ?? undefined,
      isRead: notificationFilter === "unread" ? false : undefined,
      projectId: notificationProjectFilter || undefined,
      sort: "created_at",
      direction: "desc",
    })
      .then((result) => {
        setNotifications({ status: "ready", data: result.items, error: null });
        setNotificationNextCursor(result.next_cursor);
      })
      .catch((error: unknown) => {
        setNotifications((current) => ({
          status: "error",
          data: current.data,
          error: error instanceof Error ? error.message : "Notifications could not be loaded.",
        }));
      });
  }, [notificationCursor, notificationFilter, notificationProjectFilter, session.data?.token]);
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
    void refreshProviders();
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
    setAssetCursor(null);
    setAssetCursorHistory([]);
    setSelectedAssetId(null);
    assetExplicitlyCleared.current = false;
  }, [selectedProjectId]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedProjectId || (view !== "project" && view !== "home")) {
      setAssets(createLoadable([]));
      setAssetNextCursor(null);
      return;
    }
    setAssets((current) => ({ ...current, status: "loading", error: null }));
    listAssetsPage(token, selectedProjectId, {
      limit: 25,
      cursor: assetCursor ?? undefined,
      status: assetStatusFilter || undefined,
      query: assetFilterQuery || undefined,
      sort: assetSort,
      direction: assetDirection,
    })
      .then((result) => {
        setAssets({ status: "ready", data: result.items, error: null });
        setAssetNextCursor(result.next_cursor);
      })
      .catch((error: unknown) => {
        setAssets((current) => ({
          status: "error",
          data: current.data,
          error: error instanceof Error ? error.message : "Assets could not be loaded.",
        }));
      });
  }, [
    assetCursor,
    assetDirection,
    assetFilterQuery,
    assetSort,
    assetStatusFilter,
    selectedProjectId,
    session.data?.token,
    view,
  ]);

  // Default to the first Asset when viewing any Project tab with a loaded list and nothing
  // selected -- Collaboration, for instance, shows state for "whichever Asset is current"
  // without addressing one via its own URL. Driven by projectTab/assets.data directly (not
  // the list fetch's own resolution) so it fires correctly regardless of whether the tab
  // switch or the fetch resolves first. Only asset-aware tabs navigate to reflect the
  // default in the URL; elsewhere it's a plain state update, matching how ProjectTabs only
  // carries the current selection into asset-aware tabs when the user switches tabs.
  useEffect(() => {
    if (
      view !== "project" ||
      selectedAssetId ||
      assetExplicitlyCleared.current ||
      assets.status !== "ready" ||
      !assets.data[0]
    ) {
      return;
    }
    const fallbackAssetId = assets.data[0].id;
    startTransition(() => {
      if (ASSET_AWARE_PROJECT_TABS.has(projectTab)) {
        selectAsset(fallbackAssetId, { tab: projectTab, replace: true });
      } else {
        setSelectedAssetId(fallbackAssetId);
      }
    });
  }, [view, projectTab, selectedAssetId, assets.status, assets.data, selectAsset]);

  useEffect(() => {
    const token = session.data?.token;
    if (!token || !selectedProjectId || view !== "project") {
      setAssetViews(createLoadable([]));
      return;
    }
    setAssetViews((current) => ({ ...current, status: "loading", error: null }));
    listProjectAssetViews(token, selectedProjectId)
      .then((result) => setAssetViews({ status: "ready", data: result, error: null }))
      .catch((error: unknown) =>
        setAssetViews((current) => ({
          status: "error",
          data: current.data,
          error: error instanceof Error ? error.message : "Saved views could not be loaded.",
        })),
      );
  }, [selectedProjectId, session.data?.token, view]);
  useEffect(() => {
    const token = session.data?.token;
    analysisOperation.current += 1;
    setBusyAction((current) => current?.startsWith("provider-analysis-") ? null : current);
    setAnalysisResult(null);
    setAnalysisRepresentationId("");
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
  const analysisBusy = busyAction?.startsWith("provider-analysis-") ?? false;
  const assetNameById = new Map(assets.data.map((asset) => [asset.id, asset.name]));
  const organizationOwnerCount = organizationMembers.data.filter((membership) => membership.role === "Owner").length;
  const projectOwnerCount = projectMembers.data.filter((membership) => membership.role === "Owner").length;
  const normalizedMemberQuery = memberQuery.trim().toLowerCase();
  const matchesMemberQuery = (membership: OrganizationMembership | ProjectMembership) =>
    !normalizedMemberQuery || [membership.user?.display_name, membership.user?.email, membership.role]
      .some((value) => value?.toLowerCase().includes(normalizedMemberQuery));
  const userNameById = new Map<string, string>();
  for (const membership of [...organizationMembers.data, ...projectMembers.data]) {
    if (membership.user) userNameById.set(membership.user.id, membership.user.display_name);
  }
  if (session.data?.user) userNameById.set(session.data.user.id, session.data.user.display_name);
  const describeActor = (userId: string | null) =>
    !userId ? "System" : userId === session.data?.user.id ? "You" : userNameById.get(userId) ?? "Unknown member";
  const filteredPlugins = plugins.data.filter((plugin) => {
    const query = pluginQuery.trim().toLowerCase();
    const matchesQuery = !query || [plugin.name, plugin.id, plugin.plugin_type, ...plugin.capabilities]
      .some((value) => value.toLowerCase().includes(query));
    return matchesQuery && (pluginLifecycleFilter === "all" || plugin.lifecycle_state === pluginLifecycleFilter);
  });

  function updateAssetFilters(
    patch: Partial<Record<"q" | "status" | "sort" | "direction", string>>,
  ): void {
    const next = new URLSearchParams(location.search);
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setAssetCursor(null);
    setAssetCursorHistory([]);
    navigate({ pathname: location.pathname, search: next.toString() ? `?${next}` : "" }, { replace: true });
  }

  function handleNextAssetPage(): void {
    if (!assetNextCursor) return;
    setAssetCursorHistory((current) => [...current, assetCursor ?? ""]);
    setAssetCursor(assetNextCursor);
  }

  function handlePreviousAssetPage(): void {
    const previous = assetCursorHistory.at(-1);
    if (previous === undefined) return;
    setAssetCursorHistory((current) => current.slice(0, -1));
    setAssetCursor(previous || null);
  }

  async function handleSaveAssetView(): Promise<void> {
    if (!session.data?.token || !selectedProjectId || !assetViewName.trim()) return;
    setBusyAction("save-asset-view");
    setBanner(null);
    try {
      const created = await createProjectAssetView(session.data.token, {
        project_id: selectedProjectId,
        name: assetViewName.trim(),
        filters: { status: assetStatusFilter || null, query: assetFilterQuery || null },
        sort: { field: assetSort, direction: assetDirection },
        density: "compact",
        selected_columns: ["name", "status", "updated_at"],
      });
      setAssetViews((current) => ({
        status: "ready",
        error: null,
        data: [...current.data, created].sort((left, right) => left.name.localeCompare(right.name)),
      }));
      setAssetViewName("");
      setBanner(`Saved view “${created.name}” created.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Saved view could not be created.");
    } finally {
      setBusyAction(null);
    }
  }

  function handleApplyAssetView(savedView: ProjectAssetView): void {
    updateAssetFilters({
      q: typeof savedView.filters.query === "string" ? savedView.filters.query : "",
      status: typeof savedView.filters.status === "string" ? savedView.filters.status : "",
      sort: savedView.sort.field,
      direction: savedView.sort.direction,
    });
    setBanner(`Saved view “${savedView.name}” applied.`);
  }

  async function handleDeleteAssetView(savedView: ProjectAssetView): Promise<void> {
    if (!session.data?.token || !window.confirm(`Delete saved view “${savedView.name}”?`)) return;
    setBusyAction(`delete-asset-view-${savedView.id}`);
    try {
      await deleteProjectAssetView(session.data.token, savedView.id);
      setAssetViews((current) => ({
        status: "ready",
        error: null,
        data: current.data.filter((item) => item.id !== savedView.id),
      }));
      setBanner(`Saved view “${savedView.name}” deleted.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Saved view could not be deleted.");
    } finally {
      setBusyAction(null);
    }
  }

  function toggleNotificationSelection(notificationId: string): void {
    setSelectedNotificationIds((current) =>
      current.includes(notificationId)
        ? current.filter((item) => item !== notificationId)
        : [...current, notificationId],
    );
  }

  function handleNextNotificationPage(): void {
    if (!notificationNextCursor) return;
    setNotificationCursorHistory((current) => [...current, notificationCursor ?? ""]);
    setNotificationCursor(notificationNextCursor);
  }

  function handlePreviousNotificationPage(): void {
    const previous = notificationCursorHistory.at(-1);
    if (previous === undefined) return;
    setNotificationCursorHistory((current) => current.slice(0, -1));
    setNotificationCursor(previous || null);
  }

  async function handleBatchNotificationRead(allMatching: boolean): Promise<void> {
    if (!session.data?.token || (!allMatching && selectedNotificationIds.length === 0)) return;
    setBusyAction(allMatching ? "read-all-notifications" : "read-selected-notifications");
    setBanner(null);
    try {
      const result = await markNotificationsRead(
        session.data.token,
        allMatching
          ? { all_matching: true, is_read: false, project_id: notificationProjectFilter || undefined }
          : { notification_ids: selectedNotificationIds },
      );
      setSelectedNotificationIds([]);
      setNotificationCursor(null);
      setNotificationCursorHistory([]);
      await refreshNotifications(session.data.token);
      setBanner(`${result.updated_count} notification${result.updated_count === 1 ? "" : "s"} marked as read.`);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Notifications could not be updated.");
    } finally {
      setBusyAction(null);
    }
  }
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
    const membership = organizationMembers.data.find((item) => item.id === membershipId);
    if (!membership || membership.role === role) return;
    if (membership.role === "Owner" && organizationOwnerCount === 1) {
      setBanner("Assign another Organization Owner before changing the final Owner role.");
      return;
    }
    const approved = window.confirm(
      `Review Organization role change for ${membership.user?.display_name ?? "this member"}:\n\n${membership.role} → ${role}\n\n${ROLE_IMPACT[role]}`,
    );
    if (!approved) return;    setBusyAction(`organization-role-${membershipId}`);
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
    if (membership.role === "Owner" && organizationOwnerCount === 1) {
      setBanner("The final Organization Owner cannot be removed. Assign another Owner first.");
      return;
    }
    if (!window.confirm(`Remove ${membership.user?.display_name ?? "this user"} from the Organization?\n\nTheir Organization and inherited workspace access will be revoked.`)) return;
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
    const membership = projectMembers.data.find((item) => item.id === membershipId);
    if (!membership || membership.role === role) return;
    if (membership.role === "Owner" && projectOwnerCount === 1) {
      setBanner("Assign another Project Owner before changing the final Owner role.");
      return;
    }
    const approved = window.confirm(
      `Review Project role change for ${membership.user?.display_name ?? "this member"}:\n\n${membership.role} → ${role}\n\n${ROLE_IMPACT[role]}`,
    );
    if (!approved) return;    setBusyAction(`project-role-${membershipId}`);
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
    if (membership.role === "Owner" && projectOwnerCount === 1) {
      setBanner("The final Project Owner cannot be removed. Assign another Owner first.");
      return;
    }
    if (!window.confirm(`Remove ${membership.user?.display_name ?? "this user"} from the Project?\n\nOrganization membership is retained, but Project access is revoked.`)) return;
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

  async function refreshAssetPage(token: string, projectId: string): Promise<void> {
    const refreshed = await listAssetsPage(token, projectId, {
      limit: 25,
      cursor: assetCursor ?? undefined,
      status: assetStatusFilter || undefined,
      query: assetFilterQuery || undefined,
      sort: assetSort,
      direction: assetDirection,
    });
    setAssets({ status: "ready", data: refreshed.items, error: null });
    setAssetNextCursor(refreshed.next_cursor);
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
      selectAsset(asset.id);
      setBanner("Engineering Asset created.");
      await refreshAssetPage(session.data.token, selectedProjectId);
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Asset could not be created.");
    } finally {
      setBusyAction(null);
    }
  }

  async function refreshNotifications(token: string): Promise<void> {
    const refreshed = await listNotificationsPage(token, {
      limit: 50,
      cursor: notificationCursor ?? undefined,
      isRead: notificationFilter === "unread" ? false : undefined,
      projectId: notificationProjectFilter || undefined,
      sort: "created_at",
      direction: "desc",
    });
    setNotifications({ status: "ready", data: refreshed.items, error: null });
    setNotificationNextCursor(refreshed.next_cursor);
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
    const userId = session.data.user.id;
    const storedRecovery = loadTransferRecovery(userId, selectedAssetId);
    const recovery = loadTransferRecovery(userId, selectedAssetId, uploadForm.file);
    const reusableBlob = transfer.blob && transfer.assetId === selectedAssetId &&
      canReuseCompletedBlob(userId, selectedAssetId, uploadForm.file, transfer.blob.id, transfer.recovery)
      ? transfer.blob : null;
    if (!reusableBlob && storedRecovery && !recovery) {
      setTransfer({ phase: "awaiting-file", receivedBytes: 0, totalBytes: storedRecovery.fileSize,
        message: `Select the original ${storedRecovery.fileName} file to resume safely.`, blob: null,
        assetId: selectedAssetId, recovery: storedRecovery });
      setBusyAction(null);
      return;
    }
    const controller = new AbortController();
    const operation = ++transferOperation.current;
    activeTransferOperation.current = { id: operation, controller };
    setTransfer({ phase: "preparing", receivedBytes: 0, totalBytes: uploadForm.file.size,
      message: reusableBlob ? "Retrying Revision creation with the verified Blob." : "Creating a bounded upload session.",
      blob: reusableBlob, assetId: selectedAssetId, recovery });
    try {
      let blob = reusableBlob;
      if (!blob) {
        const completed = await resumableUpload({
          token: session.data.token,
          userId,
          assetId: selectedAssetId,
          file: uploadForm.file,
          recovery,
          signal: controller.signal,
          onProgress: (receivedBytes, totalBytes) => {
            if (operation === transferOperation.current) setTransfer((current) => ({
              ...current, phase: "uploading", receivedBytes, totalBytes,
              message: `${receivedBytes.toLocaleString()} of ${totalBytes.toLocaleString()} bytes confirmed by the server.`,
            }));
          },
          onVerifying: () => {
            if (operation === transferOperation.current) setTransfer((current) => ({ ...current, phase: "verifying",
              message: "The server is assembling and verifying the file." }));
          },
        });
        blob = completed.blob!;
      }
      if (operation !== transferOperation.current || controller.signal.aborted) {
        throw new DOMException("Transfer cancelled.", "AbortError");
      }
      const completedRecovery = loadTransferRecovery(userId, selectedAssetId, uploadForm.file);
      setTransfer((current) => ({ ...current, phase: "checking-in",
        message: "The verified Blob is being attached to a new Revision.", blob,
        assetId: selectedAssetId, recovery: completedRecovery }));
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
      if (operation !== transferOperation.current) return;
      clearTransferRecovery(userId, selectedAssetId);
      setUploadForm({ file: null, comment: "", representationName: "" });
      setTransfer((current) => ({ ...current, phase: "success",
        message: "The new immutable Revision is ready.", blob: null, recovery: null }));
      setBanner("Changes checked in as a new immutable Revision.");
      try {
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
        await refreshAssetPage(session.data.token, selectedProjectId!);
      } catch {
        setBanner("The Revision was created, but the workspace could not refresh. Reload to see the latest state.");
      }
    } catch (error: unknown) {
      if (operation !== transferOperation.current) return;
      if (error instanceof DOMException && error.name === "AbortError") {
        setTransfer((current) => ({ ...current, phase: "cancelled", message: "No incomplete content became a Blob." }));
        return;
      }
      setTransfer((current) => ({ ...current, phase: "failed",
        message: error instanceof Error ? error.message : "The check-in could not be completed.",
        recovery: loadTransferRecovery(userId, selectedAssetId) }));
      if (error instanceof ApiError) {
        await refreshNotifications(session.data.token);
        setCollaborationError(error);
        setBanner(collaborationGuidance(error));
      } else {
        setBanner(error instanceof Error ? error.message : "Upload failed.");
      }
    } finally {
      if (activeTransferOperation.current?.id === operation) {
        activeTransferOperation.current = null;
        setBusyAction(null);
      }
    }
  }

  function handleUploadFileChange(file: File | null): void {
    setUploadForm((current) => ({
      ...current,
      file,
      representationName: current.representationName || file?.name || "",
    }));
    if (!file || !selectedAssetId) {
      setTransfer((current) => ({ ...current, blob: null }));
      return;
    }
    const userId = session.data?.user.id;
    const recovery = userId ? loadTransferRecovery(userId, selectedAssetId, file) : null;
    setTransfer({
      phase: recovery ? "preparing" : "idle",
      receivedBytes: 0,
      totalBytes: file.size,
      message: recovery ? "The original file matches. Submit to resume from server-confirmed chunks." : null,
      blob: null, assetId: selectedAssetId, recovery,
    });
  }

  async function handleCancelTransfer(): Promise<void> {
    transferOperation.current += 1;
    activeTransferOperation.current?.controller.abort();
    activeTransferOperation.current = null;
    const userId = session.data?.user.id;
    const token = session.data?.token;
    const assetId = selectedAssetId;
    const recovery = userId && assetId ? loadTransferRecovery(userId, assetId) : null;
    if (userId && assetId) clearTransferRecovery(userId, assetId);
    if (token && recovery) {
      void cancelBlobUploadSession(token, recovery.sessionId).catch(() => {
        // Local cancellation is terminal; remote expiry or an already-finished session is equivalent.
      });
    }
    setTransfer((current) => ({ ...current, phase: "cancelled", message: "The upload session was cancelled.",
      blob: null, recovery: null }));
    setBusyAction(null);
  }

  async function handleDiscardTransfer(): Promise<void> {
    transferOperation.current += 1;
    activeTransferOperation.current?.controller.abort();
    activeTransferOperation.current = null;
    const userId = session.data?.user.id;
    const token = session.data?.token;
    const assetId = selectedAssetId;
    const recovery = userId && assetId ? loadTransferRecovery(userId, assetId) : null;
    if (userId && assetId) clearTransferRecovery(userId, assetId);
    if (recovery && token) {
      void cancelBlobUploadSession(token, recovery.sessionId).catch(() => {
        // Discard is local and immediate; a delayed terminal response cannot own current UI state.
      });
    }
    setUploadForm((current) => ({ ...current, file: null }));
    setTransfer({ phase: "idle", receivedBytes: 0, totalBytes: 0, message: null,
      blob: null, assetId: selectedAssetId, recovery: null });
    setBusyAction(null);
  }

  function handleRetryCheckin(): void {
    const form = document.querySelector<HTMLFormElement>("form[data-checkin-form]");
    form?.requestSubmit();
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
          listAssetsPage(session.data.token, selectedProjectId, {
            limit: 25,
            cursor: assetCursor ?? undefined,
            status: assetStatusFilter || undefined,
            query: assetFilterQuery || undefined,
            sort: assetSort,
            direction: assetDirection,
          }),
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
      setAssets({ status: "ready", data: refreshedAssets.items, error: null });
      setAssetNextCursor(refreshedAssets.next_cursor);
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

  async function refreshProviders(): Promise<void> {
    const token = session.data?.token;
    if (!token) {
      setProviders(createLoadable([]));
      setProviderOptions({});
      return;
    }
    try {
      const result = await discoverProviders(token);
      setProviders({ status: "ready", data: result, error: null });
      if (!selectedProjectId || !selectedOrganizationId) {
        setProviderOptions({});
        return;
      }
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
    } catch (error: unknown) {
      setProviders({
        status: "error",
        data: [],
        error: error instanceof Error ? error.message : "Providers could not be discovered.",
      });
    }
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

  async function handleInvokeAnalysisProvider(provider: ProviderDescriptor): Promise<void> {
    if (
      !session.data?.token ||
      !selectedAssetId ||
      !selectedProjectId ||
      !selectedOrganizationId ||
      !selectedAnalysisRepresentation
    ) return;
    const operation = analysisOperation.current + 1;
    analysisOperation.current = operation;
    setBusyAction(`provider-analysis-${provider.id}`);
    setBanner(null);
    setAnalysisResult(null);
    try {
      const result = await invokeAnalysisProvider(session.data.token, provider.id, {
        representation_id: selectedAnalysisRepresentation.id,
        project_id: selectedProjectId,
        organization_id: selectedOrganizationId,
      });
      const [metadata, relationships, incoming, outgoing, references, graph] = await Promise.all([
        listMetadata(session.data.token, "asset", selectedAssetId),
        listAssetRelationships(session.data.token, selectedAssetId),
        listIncomingAssetRelationships(session.data.token, selectedAssetId),
        listOutgoingAssetRelationships(session.data.token, selectedAssetId),
        listAssetReferences(session.data.token, selectedAssetId),
        getAssetGraph(session.data.token, selectedAssetId, { direction: "both", maxDepth: 3 }),
      ]);
      if (operation !== analysisOperation.current) return;
      setAssetMetadata({ status: "ready", data: metadata, error: null });
      setAssetRelationships({ status: "ready", data: relationships, error: null });
      setIncomingRelationships({ status: "ready", data: incoming, error: null });
      setOutgoingRelationships({ status: "ready", data: outgoing, error: null });
      setAssetReferences({ status: "ready", data: references, error: null });
      setAssetGraph({ status: "ready", data: graph, error: null });
      setAnalysisResult(result);
      setBanner(`${provider.name} analysis completed.`);
    } catch (error: unknown) {
      if (operation !== analysisOperation.current) return;
      setAnalysisResult(null);
      setBanner(error instanceof Error ? error.message : "Analysis Provider invocation failed.");
    } finally {
      if (operation === analysisOperation.current) setBusyAction(null);
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
      await refreshProviders();
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
    setPluginConfigurationErrors((current) => ({ ...current, [pluginId]: null }));
    try {
      const configuration = await getPluginConfiguration(session.data.token, pluginId);
      setPluginConfigurations((current) => ({ ...current, [pluginId]: configuration }));
      setPluginConfigurationDrafts((current) => ({ ...current, [pluginId]: { ...configuration.values } }));
      setPluginConfigurationJson((current) => ({
        ...current,
        [pluginId]: JSON.stringify(configuration.values, null, 2),
      }));
    } catch (error: unknown) {
      setBanner(error instanceof Error ? error.message : "Plugin configuration could not be loaded.");
    } finally {
      setBusyAction(null);
    }
  }

  function updatePluginConfigurationField(pluginId: string, key: string, value: unknown): void {
    setPluginConfigurationDrafts((current) => ({
      ...current,
      [pluginId]: { ...(current[pluginId] ?? {}), [key]: value },
    }));
    setPluginConfigurationErrors((current) => ({ ...current, [pluginId]: null }));
  }

  async function handleSavePluginConfiguration(pluginId: string): Promise<void> {
    if (!session.data?.token) return;
    const configuration = pluginConfigurations[pluginId];
    if (!configuration) return;
    setBusyAction(`plugin-config-save-${pluginId}`);
    setBanner(null);
    setPluginConfigurationErrors((current) => ({ ...current, [pluginId]: null }));
    try {
      let values: Record<string, unknown>;
      if (supportsSchemaForm(configuration)) {
        values = pluginConfigurationDrafts[pluginId] ?? {};
      } else {
        const parsed = JSON.parse(pluginConfigurationJson[pluginId] ?? "{}");
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("Advanced configuration must be a JSON object.");
        }
        values = parsed as Record<string, unknown>;
      }
      const saved = await updatePluginConfiguration(session.data.token, pluginId, values);
      setPluginConfigurations((current) => ({ ...current, [pluginId]: saved }));
      setPluginConfigurationDrafts((current) => ({ ...current, [pluginId]: { ...saved.values } }));
      setPluginConfigurationJson((current) => ({ ...current, [pluginId]: JSON.stringify(saved.values, null, 2) }));
      await refreshPlugins();
      setBanner("Plugin configuration saved. Secret values remain write-only.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Plugin configuration is not valid.";
      setPluginConfigurationErrors((current) => ({ ...current, [pluginId]: message }));
    } finally {
      setBusyAction(null);
    }
  }
  async function handleRemovePlugin(plugin: PluginRecord): Promise<void> {
    if (!session.data?.token) return;
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
    <AppShell
      announcement={banner}
      header={
        isAuthenticated && session.data ? (
          <AuthenticatedHeader
            apiError={foundation.error}
            apiLabel={foundation.data?.phase ?? "Connecting to API"}
            apiStatus={foundation.status}
            displayName={session.data.user.display_name}
            email={session.data.user.email}
            onHome={() => navigate("/")}
            onNotifications={() => navigate("/notifications")}
            onOpenNavigation={() => setMobileNavigationOpen(true)}
            onSignOut={() => void handleSignOut()}
            unreadNotifications={unreadNotifications}
          />
        ) : (
          <GuestHeader foundation={foundation} />
        )
      }
    >
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
            {authError ? <InlineAlert tone="danger">{authError}</InlineAlert> : null}
            {session.error ? <InlineAlert tone="danger">{session.error}</InlineAlert> : null}
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

              <button
                className={view === "notifications" ? "sidebar-link is-active" : "sidebar-link"}
                onClick={() => { setMobileNavigationOpen(false); navigate("/notifications"); }}
                type="button"
              >
                <Inbox /> Notifications <span>{unreadNotifications}</span>
              </button>

              <button className={view === "projects" ? "sidebar-link is-active" : "sidebar-link"} onClick={() => { setMobileNavigationOpen(false); navigate("/projects"); }} type="button"><FolderKanban /> Projects <span>{projects.data.length}</span></button>

              {organizations.status === "error" ? (
                <InlineAlert tone="danger">{organizations.error}</InlineAlert>
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
                    <InlineAlert tone="danger">{projects.error}</InlineAlert>
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
                  {view === "home" ? (
                    <article className="detail-card">
                      <h3>Recent Engineering Assets</h3>
                      <p>{selectedProjectId ? "Updated in the selected Project" : "Select a Project to load recent Assets"}</p>
                      <ul className="home-list">
                        {assets.data.slice(0, 6).map((asset) => (
                          <li key={asset.id}>
                            <button
                              className="text-button"
                              onClick={() => {
                                setSelectedAssetId(asset.id);
                                navigate(projectAssetPath(asset.project_id, "assets", asset.id));
                              }}
                              type="button"
                            >
                              {asset.name}
                            </button>
                            <span>{asset.status} · {formatTimestamp(asset.updated_at)}</span>
                          </li>
                        ))}
                      </ul>
                    </article>
                  ) : null}                </div>

                {view === "home" && (organizations.status === "loading" || projects.status === "loading" || assets.status === "loading" || notifications.status === "loading") ? (
                  <InlineAlert tone="info"><RefreshCw aria-hidden="true" /> Refreshing operational context…</InlineAlert>
                ) : null}
                {view === "home" && (organizations.status === "error" || projects.status === "error" || assets.status === "error" || notifications.status === "error") ? (
                  <article className="detail-card recovery-card" role="alert">
                    <h3>Some workspace data needs attention</h3>
                    <p>{organizations.error ?? projects.error ?? assets.error ?? notifications.error}</p>
                    <p className="muted-text">Available data remains visible. Retry the affected workspace or verify that your permissions have not changed.</p>
                  </article>
                ) : null}
                {view === "home" && !selectedProjectId && projects.status === "ready" ? (
                  <div className="empty-state operational-empty"><FolderKanban aria-hidden="true" /><h3>No recent Project context</h3><p>Create or select a Project to surface recent Engineering Assets here.</p></div>
                ) : null}
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

            {view === "notifications" ? (
              <section aria-labelledby="notifications-workspace-title" className="panel notifications-workspace content-span">
                <header className="panel-header operational-header">
                  <div>
                    <p className="eyebrow">Event inbox</p>
                    <h2 id="notifications-workspace-title">Notifications</h2>
                    <p className="muted-text">Review collaboration events, acknowledge a selected set, or clear the complete unread queue.</p>
                  </div>
                  <div className="filter-cluster" aria-label="Notification filters">
                    <label className="inline-filter">
                      Project
                      <select
                        value={notificationProjectFilter}
                        onChange={(event) => {
                          setNotificationProjectFilter(event.target.value);
                          setNotificationCursor(null);
                          setNotificationCursorHistory([]);
                          setSelectedNotificationIds([]);
                        }}
                      >
                        <option value="">All Projects</option>
                        {projects.data.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                      </select>
                    </label>
                    <label className="inline-filter">
                      Show
                      <select
                        value={notificationFilter}
                        onChange={(event) => {
                          setNotificationFilter(event.target.value as "all" | "unread");
                          setNotificationCursor(null);
                          setNotificationCursorHistory([]);
                          setSelectedNotificationIds([]);
                        }}
                      >
                        <option value="unread">Unread</option>
                        <option value="all">All events</option>
                      </select>
                    </label>
                  </div>
                </header>

                <div className="selection-toolbar" aria-label="Notification batch actions">
                  <span>{selectedNotificationIds.length} selected</span>
                  <button
                    className="secondary-button"
                    onClick={() =>
                      setSelectedNotificationIds(
                        selectedNotificationIds.length === notifications.data.filter((item) => !item.is_read).length
                          ? []
                          : notifications.data.filter((item) => !item.is_read).map((item) => item.id),
                      )
                    }
                    type="button"
                  >
                    Select page
                  </button>
                  <button
                    className="secondary-button"
                    disabled={selectedNotificationIds.length === 0 || busyAction === "read-selected-notifications"}
                    onClick={() => void handleBatchNotificationRead(false)}
                    type="button"
                  >
                    Mark selected read
                  </button>
                  <button
                    className="primary-button"
                    disabled={busyAction === "read-all-notifications" || unreadNotifications === 0}
                    onClick={() => void handleBatchNotificationRead(true)}
                    type="button"
                  >
                    Mark all matching read
                  </button>
                </div>

                {notifications.status === "error" ? (
                  <InlineAlert
                    title={notifications.data.length ? "Showing stale notifications" : "Notifications unavailable"}
                    tone="danger"
                  >
                    <span>{notifications.error}</span>
                    <button className="secondary-button" onClick={() => void handleRefreshNotifications()} type="button">Retry</button>
                  </InlineAlert>
                ) : null}
                {notifications.status === "loading" ? (
                  <InlineAlert tone="info">
                    <RefreshCw aria-hidden="true" />
                    <span>{notifications.data.length ? "Refreshing while the current page stays available…" : "Loading notifications…"}</span>
                  </InlineAlert>
                ) : null}

                {notifications.data.length ? (
                  <div className="notification-queue" aria-busy={notifications.status === "loading"}>
                    {notifications.data.map((notification) => (
                      <article className={notification.is_read ? "notification-row" : "notification-row is-unread"} key={notification.id}>
                        <input
                          aria-label={`Select ${formatNotificationEvent(notification.event_type)}`}
                          checked={selectedNotificationIds.includes(notification.id)}
                          disabled={notification.is_read}
                          onChange={() => toggleNotificationSelection(notification.id)}
                          type="checkbox"
                        />
                        <div className="notification-copy">
                          <strong>{formatNotificationEvent(notification.event_type)}</strong>
                          <span>{notificationSummary(notification)}</span>
                          <small>{formatTimestamp(notification.created_at)}</small>
                        </div>
                        <span className={`status-pill notification-pill ${notification.is_read ? "notification-read" : "notification-unread"}`}>
                          {notification.is_read ? "read" : "unread"}
                        </span>
                        {!notification.is_read ? (
                          <button className="secondary-button" onClick={() => void handleMarkNotificationRead(notification.id)} type="button">Mark read</button>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : notifications.status === "ready" ? (
                  <div className="empty-state operational-empty">
                    <Bell aria-hidden="true" />
                    <h3>{notificationFilter === "unread" ? "Unread queue is clear" : "No notifications yet"}</h3>
                    <p>New collaboration and lifecycle events will appear here when they target your account.</p>
                  </div>
                ) : null}

                <nav aria-label="Notification pages" className="pagination-bar">
                  <button className="secondary-button" disabled={notificationCursorHistory.length === 0} onClick={handlePreviousNotificationPage} type="button"><ArrowLeft /> Previous</button>
                  <span>Page {notificationCursorHistory.length + 1}</span>
                  <button className="secondary-button" disabled={!notificationNextCursor} onClick={handleNextNotificationPage} type="button">Next <ArrowRight /></button>
                </nav>
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
                {plugins.status === "error" ? <InlineAlert tone="danger">{plugins.error}</InlineAlert> : null}
                <div className="governance-filter-bar" aria-label="Plugin filters">
                  <label>Search plugins<input type="search" placeholder="Name, identifier or capability" value={pluginQuery} onChange={(event) => setPluginQuery(event.target.value)} /></label>
                  <label>Lifecycle<select value={pluginLifecycleFilter} onChange={(event) => setPluginLifecycleFilter(event.target.value)}><option value="all">All states</option>{[...new Set(plugins.data.map((plugin) => plugin.lifecycle_state))].map((state) => <option key={state} value={state}>{state}</option>)}</select></label>
                </div>
                <p className="muted-text governance-result-count" aria-live="polite">{filteredPlugins.length} of {plugins.data.length} plugins shown. Official Plugins and Community Plugins follow the same lifecycle controls.</p>
                <div className="plugin-grid">
                  {filteredPlugins.map((plugin) => {
                    const configuration = pluginConfigurations[plugin.id];
                    const draft = pluginConfigurationDrafts[plugin.id] ?? {};
                    const properties = configuration ? configurationProperties(configuration) : {};
                    const required = Array.isArray(configuration?.configuration_schema?.required) ? configuration.configuration_schema.required as string[] : [];
                    return (
                    <article className="detail-card plugin-card" key={plugin.id}>
                      <div className="detail-row"><div><p className="eyebrow">{plugin.plugin_type} plugin</p><h3>{plugin.name}</h3><p>{plugin.id} · v{plugin.version}</p></div><span className={`status-pill plugin-state-${plugin.lifecycle_state}`}>{plugin.lifecycle_state}</span></div>
                      <div className="capability-list" aria-label="Declared capabilities">{plugin.capabilities.map((capability) => <span key={capability}>{capability}</span>)}</div>
                      {plugin.diagnostic_reason ? <InlineAlert tone="warning">{plugin.diagnostic_reason}</InlineAlert> : null}
                      <details className="manifest-review"><summary>Review manifest and package evidence</summary><dl><div><dt>Extension API</dt><dd>{plugin.extension_api_versions.join(", ") || "Not declared"}</dd></div><div><dt>Package digest</dt><dd><code>{plugin.package_digest}</code></dd></div><div><dt>Installed</dt><dd>{formatTimestamp(plugin.created_at)}</dd></div><div><dt>Last changed</dt><dd>{formatTimestamp(plugin.updated_at)}</dd></div></dl></details>
                      <div className="collaboration-actions">
                        <ConfirmDialog confirmLabel={plugin.enabled ? "Disable plugin" : "Enable plugin"} description={`${plugin.enabled ? "Disable" : "Enable"} ${plugin.name}. Declared capabilities: ${plugin.capabilities.join(", ") || "none"}. This audited lifecycle change uses the same Extension API path for Official and Community Plugins.`} onConfirm={() => void handlePluginState(plugin)} title={`Review ${plugin.enabled ? "disable" : "enable"} action`} trigger={<button className="secondary-button" disabled={busyAction === `plugin-state-${plugin.id}`} type="button">{plugin.enabled ? "Disable" : "Enable"}</button>} />
                        <button className="secondary-button" disabled={busyAction === `plugin-config-load-${plugin.id}`} onClick={() => void handleLoadPluginConfiguration(plugin.id)} type="button">{configuration ? "Reset configuration" : "Configure"}</button>
                        <ConfirmDialog confirmLabel="Remove plugin" description={`Remove ${plugin.name}. Immutable package evidence and audit history will be retained. Enabled plugins must be disabled first.`} onConfirm={() => void handleRemovePlugin(plugin)} title="Review plugin removal" trigger={<button className="secondary-button warning-button" disabled={plugin.enabled || busyAction === `plugin-remove-${plugin.id}`} type="button">Remove</button>} />
                      </div>
                      <div className="plugin-upgrade-row"><label>Same-identity upgrade package<input accept=".openpdm-plugin,application/zip" disabled={plugin.enabled} type="file" onChange={(event) => setPluginUpgradePackages((current) => ({ ...current, [plugin.id]: event.target.files?.[0] ?? null }))} /></label><button className="secondary-button" disabled={plugin.enabled || !pluginUpgradePackages[plugin.id] || busyAction === `plugin-upgrade-${plugin.id}`} onClick={() => void handleUpgradePlugin(plugin)} type="button">{busyAction === `plugin-upgrade-${plugin.id}` ? "Upgrading..." : "Review and upgrade"}</button></div>
                      {configuration ? (
                        <section className="form-grid plugin-configuration" aria-label={`${plugin.name} configuration`}>
                          <div><h4>Configuration</h4><p className="muted-text">Schema-bounded values are validated by the Platform Core. Secrets are write-only and never read back.</p></div>
                          {supportsSchemaForm(configuration) ? Object.entries(properties).map(([key, property]) => {
                            const isSecret = property.secret === true;
                            const value = draft[key];
                            const label = property.title ?? key;
                            return (
                              <label key={key}>{label}{required.includes(key) ? " (required)" : ""}
                                {property.enum?.length ? <select value={String(value ?? "")} onChange={(event) => updatePluginConfigurationField(plugin.id, key, event.target.value)}><option value="">Select a value</option>{property.enum.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}</select> : property.type === "boolean" ? <input checked={Boolean(value)} type="checkbox" onChange={(event) => updatePluginConfigurationField(plugin.id, key, event.target.checked)} /> : <input type={isSecret ? "password" : property.type === "number" || property.type === "integer" ? "number" : "text"} value={String(value ?? "")} placeholder={isSecret && configuration.configured_secret_fields.includes(key) ? "Secret configured — enter to replace" : undefined} onChange={(event) => updatePluginConfigurationField(plugin.id, key, property.type === "number" || property.type === "integer" ? (event.target.value === "" ? "" : Number(event.target.value)) : event.target.value)} />}
                                {property.description ? <small>{property.description}</small> : null}{isSecret && configuration.configured_secret_fields.includes(key) ? <small className="secret-status">Configured · value hidden</small> : null}
                              </label>
                            );
                          }) : <label>Advanced configuration (JSON object)<textarea aria-invalid={Boolean(pluginConfigurationErrors[plugin.id])} value={pluginConfigurationJson[plugin.id] ?? "{}"} onChange={(event) => { setPluginConfigurationJson((current) => ({ ...current, [plugin.id]: event.target.value })); setPluginConfigurationErrors((current) => ({ ...current, [plugin.id]: null })); }} /><small>The manifest uses schema constructs that need the validated JSON fallback.</small></label>}
                          {pluginConfigurationErrors[plugin.id] ? <InlineAlert tone="danger">{pluginConfigurationErrors[plugin.id]}</InlineAlert> : null}
                          <div className="collaboration-actions"><button className="primary-button" disabled={busyAction === `plugin-config-save-${plugin.id}`} onClick={() => void handleSavePluginConfiguration(plugin.id)} type="button">{busyAction === `plugin-config-save-${plugin.id}` ? "Saving..." : "Save configuration"}</button><button className="secondary-button" onClick={() => void handleLoadPluginConfiguration(plugin.id)} type="button">Reset draft</button></div>
                        </section>
                      ) : null}
                    </article>
                  );})}
                </div>
                  </>
                )}
              </section>
            ) : null}

            {view === "project" ? (
              <section aria-labelledby="project-workspace-title" className="panel project-workspace content-span">
                <header className="project-header">
                  <div className="project-heading-row">
                    <div>
                      <p className="breadcrumb">
                        Projects <ChevronRight size={14} /> {projects.data.find((item) => item.id === selectedProjectId)?.name ?? "Project"}
                      </p>
                      <h2 id="project-workspace-title">{projects.data.find((item) => item.id === selectedProjectId)?.name ?? "Project workspace"}</h2>
                      <p className="muted-text">
                        {projects.data.find((item) => item.id === selectedProjectId)?.description || "Engineering collaboration workspace"}
                      </p>
                    </div>
                    <span className="status-pill">{currentProjectRole ?? "Member"}</span>
                  </div>
                  <ProjectTabs
                    onValueChange={(tab: ProjectTab) => {
                      if (selectedProjectId) {
                        // Only tabs whose content addresses a specific asset carry the
                        // current selection into their URL; other tabs stay bare even if
                        // an asset happens to be selected in the background.
                        const assetForTab = ASSET_AWARE_PROJECT_TABS.has(tab) ? selectedAssetId : null;
                        navigate(projectAssetPath(selectedProjectId, tab, assetForTab));
                      }
                    }}
                    value={projectTab}
                  />
                </header>

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
                            <button key={asset.id} onClick={() => selectAsset(asset.id, { tab: "assets" })} type="button">
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
                  <section className="panel content-span focused-panel relationships-workspace" aria-labelledby="relationships-title">
                    <header className="panel-header operational-header">
                      <div><p className="eyebrow">Asset graph</p><h2 id="relationships-title">Relationships and references</h2><p className="muted-text">Directional graph edges and unresolved or external references remain visibly distinct.</p></div>
                      <label className="inline-filter">
                        Engineering Asset
                        <select value={selectedAssetId ?? ""} onChange={(event) => selectAsset(event.target.value || null)}>
                          <option value="">Select an Asset</option>
                          {assets.data.map((asset) => <option key={asset.id} value={asset.id}>{asset.name}</option>)}
                        </select>
                      </label>
                    </header>

                    <article className="detail-card relationship-card">
                      <div className="detail-row">
                        <div>
                          <h3>Complete project graph</h3>
                          <p className="muted-text">
                            Every Engineering Asset and Asset-to-Asset relationship in this Project, merged from each
                            Asset&apos;s bounded graph read.
                          </p>
                        </div>
                        <span className="status-pill">
                          {projectGraph.data?.has_cycle ? "cycle detected" : "no cycle"}
                        </span>
                      </div>
                      {projectGraph.status === "error" ? (
                        <InlineAlert tone="danger">{projectGraph.error}</InlineAlert>
                      ) : null}
                      {projectGraph.data && projectGraph.data.nodes.length > 0 ? (
                        <>
                          <AssetGraphDiagram graph={projectGraph.data} onSelectAsset={(assetId) => selectAsset(assetId)} />
                          <p className="muted-text graph-diagram-caption">
                            {projectGraph.data.nodes.length} node{projectGraph.data.nodes.length === 1 ? "" : "s"},{" "}
                            {projectGraph.data.relationships.length} relationship
                            {projectGraph.data.relationships.length === 1 ? "" : "s"} across this Project.
                          </p>
                        </>
                      ) : projectGraph.status === "loading" ? (
                        <p className="empty-state">Loading the complete project graph...</p>
                      ) : (
                        <p className="empty-state">No Assets have relationships in this Project yet.</p>
                      )}
                    </article>

                    {assetRelationships.status === "loading" || assetReferences.status === "loading" ? (
                      <InlineAlert tone="info"><RefreshCw aria-hidden="true" /> Loading relationship context…</InlineAlert>
                    ) : null}
                    {assetRelationships.status === "error" || incomingRelationships.status === "error" || outgoingRelationships.status === "error" || assetReferences.status === "error" ? (
                      <InlineAlert title="Relationship context is partial" tone="danger"><span>{assetRelationships.error ?? incomingRelationships.error ?? outgoingRelationships.error ?? assetReferences.error}</span><button className="secondary-button" onClick={() => void handleRefreshAssetState()} type="button">Retry</button></InlineAlert>
                    ) : null}

                    {assetDetail.data ? (
                      <>
                        <div className="relationship-context-line"><strong>{assetDetail.data.name}</strong><span>{assetGraph.data?.nodes.length ?? 0} bounded nodes · depth {assetGraph.data?.max_depth ?? 3}</span></div>
                        <div className="relationship-direction-grid">
                          <section className="relationship-column" aria-labelledby="incoming-title">
                            <div className="relationship-column-header"><h3 id="incoming-title">Incoming</h3><span>{incomingRelationships.data.length}</span></div>
                            <p className="muted-text">Other Assets pointing to this Asset.</p>
                            <div className="relationship-list">
                              {incomingRelationships.data.map((relationship) => (
                                <article className="relationship-item" key={relationship.id}><div><strong>{formatRelationshipType(relationship.relationship_type)}</strong><p>{assetNameById.get(relationship.source_asset_id) ?? relationship.source_asset_id}</p><small>{formatTimestamp(relationship.created_at)}</small></div><button className="secondary-button" onClick={() => selectAsset(relationship.source_asset_id)} type="button">Open source</button></article>
                              ))}
                              {!incomingRelationships.data.length ? <p className="empty-state">No incoming relationships.</p> : null}
                            </div>
                          </section>
                          <section className="relationship-column" aria-labelledby="outgoing-title">
                            <div className="relationship-column-header"><h3 id="outgoing-title">Outgoing</h3><span>{outgoingRelationships.data.length}</span></div>
                            <p className="muted-text">This Asset pointing to other Assets.</p>
                            <div className="relationship-list">
                              {outgoingRelationships.data.map((relationship) => (
                                <article className="relationship-item" key={relationship.id}><div><strong>{formatRelationshipType(relationship.relationship_type)}</strong><p>{assetNameById.get(relationship.target_asset_id) ?? relationship.target_asset_id}</p><small>{formatTimestamp(relationship.created_at)}</small></div><button className="secondary-button" onClick={() => selectAsset(relationship.target_asset_id)} type="button">Open target</button></article>
                              ))}
                              {!outgoingRelationships.data.length ? <p className="empty-state">No outgoing relationships.</p> : null}
                            </div>
                          </section>
                          <section className="relationship-column reference-column" aria-labelledby="references-title">
                            <div className="relationship-column-header"><h3 id="references-title">References</h3><span>{assetReferences.data.length}</span></div>
                            <p className="muted-text">External or unresolved pointers; never graph edges.</p>
                            <div className="relationship-list">
                              {assetReferences.data.map((reference) => (
                                <article className="relationship-item reference-item" key={reference.id}><div><strong>{reference.label || reference.reference_type}</strong><p>{reference.target_uri}</p><small>{reference.reference_type}</small></div></article>
                              ))}
                              {!assetReferences.data.length ? <p className="empty-state">No references attached.</p> : null}
                            </div>
                          </section>
                        </div>
                        <p className="muted-text relationship-safety-note">This workspace is read-only by design. Relationship and reference mutation stays a deliberate single-record task.</p>
                      </>
                    ) : (
                      <div className="empty-state operational-empty"><Network aria-hidden="true" /><h3>Select an Engineering Asset</h3><p>Choose an Asset to separate its incoming edges, outgoing edges and references.</p></div>
                    )}
                  </section>
                ) : null}
                {projectTab === "collaboration" ? (
                  <section className="panel content-span focused-panel">
                    <header className="panel-header"><div><p className="eyebrow">Live context</p><h2>Collaboration</h2></div><Activity /></header>
                    <div className="overview-grid">
                      <article className="detail-card"><h3>Selected Asset state</h3><p>{assetDetail.data?.name ?? "No Asset selected"}</p><span className="status-pill">{collaborationState.data?.state ?? "unavailable"}</span>{collaborationState.data?.lock ? <small>Held by {describeActor(collaborationState.data.lock.owner_user_id)} for {lockAge(collaborationState.data.lock.created_at)}</small> : <small>No active lock</small>}</article>
                      <article className="detail-card"><h3>Project notifications</h3><div className="compact-list">{notifications.data.filter((item) => item.project_id === selectedProjectId).slice(0, 8).map((item) => <div key={item.id}><span>{formatNotificationEvent(item.event_type)}</span><small>{formatTimestamp(item.created_at)}</small></div>)}</div></article>
                    </div>
                  </section>
                ) : null}

                {projectTab === "members" ? (
                  <section className="panel content-span focused-panel">
                    <header className="panel-header"><div><p className="eyebrow">Access</p><h2>Members</h2></div><Users /></header>
                    <p className="muted-text">Review Organization and Project access in the routed workspace. Role changes are reviewed before they are committed.</p>
                    <div className="role-impact-grid" aria-label="Role permission summary">
                      {Object.entries(ROLE_IMPACT).map(([role, impact]) => <article key={role}><strong>{role}</strong><span>{impact}</span></article>)}
                    </div>
                    <label className="member-search">Search members<input type="search" placeholder="Name, email or role" value={memberQuery} onChange={(event) => setMemberQuery(event.target.value)} /></label>
                    <div className="members-workspace">
                  {view === "project" && projectTab === "members" && selectedOrganizationId ? (
                    <section className="membership-panel" aria-labelledby="organization-members-heading">
                      <h3 id="organization-members-heading">Organization members</h3>
                      <p className="muted-text">
                        Owners control Owner roles. Every Organization must retain an Owner.
                      </p>
                      {organizationMembers.status === "error" ? (
                        <InlineAlert tone="danger">{organizationMembers.error}</InlineAlert>
                      ) : null}
                      <div className="member-list">
                        {organizationMembers.data.filter(matchesMemberQuery).map((membership) => {
                          const isLastOwner = membership.role === "Owner" && organizationOwnerCount === 1;
                          const canManageTarget =
                            canManageOrganizationMembers &&
                            (membership.role !== "Owner" || currentOrganizationRole === "Owner");
                          return (
                            <div className="member-row" key={membership.id}>
                              <span>
                                <strong>{membership.user?.display_name ?? "Unknown user"}</strong>
                                <small>{membership.user?.email}</small>
                                {isLastOwner ? <small className="owner-safeguard">Final Owner · assign another Owner before demoting or removing</small> : null}
                              </span>
                              <select
                                aria-label={`Organization role for ${membership.user?.display_name ?? "member"}`}
                                disabled={!canManageTarget || isLastOwner || busyAction === `organization-role-${membership.id}`}
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
                                  disabled={isLastOwner || busyAction === `remove-organization-${membership.id}`}
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
                        <InlineAlert tone="danger">{projectMembers.error}</InlineAlert>
                      ) : null}
                      <div className="member-list">
                        {projectMembers.data.filter(matchesMemberQuery).map((membership) => {
                          const isLastOwner = membership.role === "Owner" && projectOwnerCount === 1;
                          const canManageTarget =
                            canManageProjectMembers &&
                            (membership.role !== "Owner" || currentProjectRole === "Owner");
                          return (
                            <div className="member-row" key={membership.id}>
                              <span>
                                <strong>{membership.user?.display_name ?? "Unknown user"}</strong>
                                <small>{membership.user?.email}</small>
                                {isLastOwner ? <small className="owner-safeguard">Final Owner · assign another Owner before demoting or removing</small> : null}
                              </span>
                              <select
                                aria-label={`Project role for ${membership.user?.display_name ?? "member"}`}
                                disabled={!canManageTarget || isLastOwner || busyAction === `project-role-${membership.id}`}
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
                                  disabled={isLastOwner || busyAction === `remove-project-${membership.id}`}
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

                    </div>
                  </section>
                ) : null}

                {projectTab === "assets" ? (
                  <>
            <section className="panel asset-panel asset-collection" aria-labelledby="asset-collection-title">
              <header className="panel-header operational-header">
                <div>
                  <p className="eyebrow">Engineering Assets</p>
                  <h2 id="asset-collection-title">Engineering Assets</h2>
                  <p className="muted-text">Filter, page and save private views without losing the selected Asset.</p>
                </div>
                <span className="status-pill">{assets.data.length} on page</span>
              </header>

              {selectedProjectId ? (
                <>
                  <div className="asset-toolbar" role="search">
                    <label className="search-field">
                      <Search aria-hidden="true" />
                      <span className="sr-only">Search Engineering Assets</span>
                      <input
                        placeholder="Search name or description"
                        value={assetFilterQuery}
                        onChange={(event) => updateAssetFilters({ q: event.target.value })}
                      />
                    </label>
                    <label>
                      Status
                      <select value={assetStatusFilter} onChange={(event) => updateAssetFilters({ status: event.target.value })}>
                        <option value="">All statuses</option>
                        <option value="draft">Draft</option>
                        <option value="active">Active</option>
                        <option value="archived">Archived</option>
                      </select>
                    </label>
                    <label>
                      Sort
                      <select value={assetSort} onChange={(event) => updateAssetFilters({ sort: event.target.value })}>
                        <option value="updated_at">Updated</option>
                        <option value="created_at">Created</option>
                        <option value="name">Name</option>
                        <option value="status">Status</option>
                      </select>
                    </label>
                    <label>
                      Direction
                      <select value={assetDirection} onChange={(event) => updateAssetFilters({ direction: event.target.value })}>
                        <option value="desc">Descending</option>
                        <option value="asc">Ascending</option>
                      </select>
                    </label>
                  </div>

                  <div className="saved-view-bar">
                    <div className="saved-view-list" aria-label="Private saved views">
                      {assetViews.data.map((savedView) => (
                        <span className="saved-view-chip" key={savedView.id}>
                          <button className="text-button" onClick={() => handleApplyAssetView(savedView)} type="button">{savedView.name}</button>
                          <button aria-label={`Delete saved view ${savedView.name}`} className="icon-button" disabled={busyAction === `delete-asset-view-${savedView.id}`} onClick={() => void handleDeleteAssetView(savedView)} type="button"><Trash2 /></button>
                        </span>
                      ))}
                    </div>
                    <div className="save-view-control">
                      <input aria-label="Saved view name" placeholder="View name" value={assetViewName} onChange={(event) => setAssetViewName(event.target.value)} />
                      <button className="secondary-button" disabled={!assetViewName.trim() || busyAction === "save-asset-view"} onClick={() => void handleSaveAssetView()} type="button"><Save /> Save view</button>
                    </div>
                  </div>

                  {assetViews.status === "error" ? <InlineAlert tone="danger">Saved views unavailable: {assetViews.error}</InlineAlert> : null}

                  <details className="create-disclosure">
                    <summary>Create Engineering Asset</summary>
                    <form className="form-grid compact-form" onSubmit={handleCreateAsset}>
                      <label>
                        Asset name
                        <input required value={assetForm.name} onChange={(event) => setAssetForm((current) => ({ ...current, name: event.target.value }))} />
                      </label>
                      <label>
                        Description
                        <textarea value={assetForm.description} onChange={(event) => setAssetForm((current) => ({ ...current, description: event.target.value }))} />
                      </label>
                      <button className="primary-button" disabled={busyAction === "create-asset"} type="submit">{busyAction === "create-asset" ? "Creating…" : "Create Asset"}</button>
                    </form>
                  </details>

                  {assets.status === "error" ? (
                    <InlineAlert
                      title={assets.data.length ? "Showing stale Asset data" : "Engineering Assets unavailable"}
                      tone="danger"
                    >
                      <span>{assets.error}</span>
                      <button className="secondary-button" onClick={() => { setAssetCursor(null); setAssetCursorHistory([]); setAssetReloadKey((current) => current + 1); }} type="button">Retry</button>
                    </InlineAlert>
                  ) : null}
                  {assets.status === "loading" ? (
                    <InlineAlert tone="info"><RefreshCw aria-hidden="true" /> {assets.data.length ? "Refreshing this page…" : "Loading Engineering Assets…"}</InlineAlert>
                  ) : null}

                  {hasAssets ? (
                    <div className="asset-table-region" aria-busy={assets.status === "loading"} tabIndex={0}>
                      <table className="asset-table">
                        <thead><tr><th>Name</th><th>Status</th><th>Updated</th></tr></thead>
                        <tbody>
                          {assets.data.map((asset) => (
                            <tr className={selectedAssetId === asset.id ? "is-selected" : ""} key={asset.id}>
                              <td><button aria-current={selectedAssetId === asset.id ? "true" : undefined} className="text-button asset-name-button" onClick={() => selectAsset(asset.id)} type="button"><strong>{asset.name}</strong><small>{asset.description || "No description"}</small></button></td>
                              <td><span className="status-pill">{asset.status}</span></td>
                              <td>{formatTimestamp(asset.updated_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : assets.status === "ready" ? (
                    <div className="empty-state operational-empty"><Boxes aria-hidden="true" /><h3>No Engineering Assets match this view</h3><p>Clear the filters or create the first generic Engineering Asset for this Project.</p></div>
                  ) : null}

                  <nav aria-label="Engineering Asset pages" className="pagination-bar">
                    <button className="secondary-button" disabled={assetCursorHistory.length === 0} onClick={handlePreviousAssetPage} type="button"><ArrowLeft /> Previous</button>
                    <span>Page {assetCursorHistory.length + 1}</span>
                    <button className="secondary-button" disabled={!assetNextCursor} onClick={handleNextAssetPage} type="button">Next <ArrowRight /></button>
                  </nav>
                </>
              ) : (
                <div className="empty-state operational-empty"><FolderKanban aria-hidden="true" /><h3>Select a Project</h3><p>Choose a Project before browsing or creating Engineering Assets.</p></div>
              )}
            </section>
            <AssetDetailPanel
              analysisBusy={analysisBusy}
              analysisRepresentations={analysisRepresentations}
              analysisResult={analysisResult}
              assetDetail={assetDetail}
              assetGraph={assetGraph}
              assetHistory={assetHistory}
              assetMetadata={assetMetadata}
              assetNameById={assetNameById}
              assetReferences={assetReferences}
              assetRelationships={assetRelationships}
              assetTimeline={assetTimeline}
              busyAction={busyAction}
              collaborationError={collaborationError}
              collaborationState={collaborationState}
              currentUserId={session.data?.user.id}
              describeActor={describeActor}
              incomingRelationships={incomingRelationships}
              notifications={notifications}
              onAnalysisRepresentationChange={setAnalysisRepresentationId}
              onApplyMetadataProvider={(provider) => void handleApplyMetadataProvider(provider)}
              onCancelTransfer={() => void handleCancelTransfer()}
              onCheckout={() => void handleCheckout()}
              onClose={() => selectAsset(null)}
              onDiscardTransfer={() => void handleDiscardTransfer()}
              onDownload={(blobId, filename) => void handleDownload(blobId, filename)}
              onInvokeAnalysisProvider={(provider) => void handleInvokeAnalysisProvider(provider)}
              onMarkNotificationRead={(notificationId) => void handleMarkNotificationRead(notificationId)}
              onProviderSelectionChange={(providerId, value) =>
                setProviderSelections((current) => ({ ...current, [providerId]: value }))
              }
              onRefreshAssetState={() => void handleRefreshAssetState()}
              onRefreshNotifications={() => void handleRefreshNotifications()}
              onRetryCheckin={handleRetryCheckin}
              onSelectAsset={(assetId) => selectAsset(assetId)}
              onSubmitUpload={handleUpload}
              onUnlock={(force) => void handleUnlock(force)}
              onUploadCommentChange={(value) =>
                setUploadForm((current) => ({ ...current, comment: value }))
              }
              onUploadFileChange={handleUploadFileChange}
              onUploadRepresentationNameChange={(value) =>
                setUploadForm((current) => ({ ...current, representationName: value }))
              }
              outgoingRelationships={outgoingRelationships}
              providerOptions={providerOptions}
              providers={providers}
              providerSelections={providerSelections}
              selectedAnalysisRepresentation={selectedAnalysisRepresentation}
              selectedAssetId={selectedAssetId}
              transfer={transfer}
              unreadNotifications={unreadNotifications}
              uploadForm={uploadForm}
            />
                  </>
                ) : null}
              </section>
            ) : null}
          </section>
        </>
      )}
    </AppShell>
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
