import { useState, type FormEvent, type ReactNode } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Download, Lock, Maximize2, Share2, Upload, X } from "lucide-react";
import { Dialog } from "../../components/primitives/Dialog";
import { formatRelativeTime, formatTimestamp } from "../../app/format";
import type { Loadable } from "../../app/loadable";
import type { Asset, BlobRecord, Revision } from "../../api";
import { AssetDetailTabs, type AssetDetailTab } from "./AssetDetailTabs";
import { AssetOverview } from "./AssetOverview";
import { MetadataAnalysisSection, type MetadataAnalysisSectionProps } from "./MetadataAnalysisSection";
import { RelationshipsGraphSection, type RelationshipsGraphSectionProps } from "./RelationshipsGraphSection";
import { HistoryCollaborationSection, type HistoryCollaborationSectionProps } from "./HistoryCollaborationSection";
import { TransferStatus, type TransferPhase } from "../transfers/TransferStatus";

type UploadForm = {
  comment: string;
  file: File | null;
  representationName: string;
};

type TransferState = {
  blob: BlobRecord | null;
  message: string | null;
  phase: TransferPhase;
  receivedBytes: number;
  totalBytes: number;
};

const ASSET_STATUSES = ["draft", "active", "archived"] as const;
type AssetStatus = (typeof ASSET_STATUSES)[number];

/**
 * "overlay" renders the sheet as a centred modal dialog (narrow viewports);
 * "dock" renders it as a persistent side column next to the asset table.
 */
export type AssetDetailPresentation = "overlay" | "dock";

type AssetDetailPanelProps = MetadataAnalysisSectionProps &
  RelationshipsGraphSectionProps &
  HistoryCollaborationSectionProps & {
    assetDetail: Loadable<Asset | null>;
    onCancelTransfer: () => void;
    onCheckInFormOpenChange: (open: boolean) => void;
    onClose: () => void;
    onDiscardTransfer: () => void;
    onOpenCheckIn: () => void;
    /** "Open as full page" — no dedicated route yet; the host explains that on click. */
    onOpenFullPage?: () => void;
    onRetryCheckin: () => void;
    onSubmitUpload: (event: FormEvent<HTMLFormElement>) => void;
    onUpdateStatus: (status: AssetStatus) => void;
    onUploadCommentChange: (value: string) => void;
    onUploadFileChange: (file: File | null) => void;
    onUploadRepresentationNameChange: (value: string) => void;
    presentation?: AssetDetailPresentation;
    selectedAssetId: string | null;
    showCheckInForm: boolean;
    transfer: TransferState;
    uploadForm: UploadForm;
  };

function FilesTab({
  revisions,
  busyAction,
  onDownload,
}: {
  revisions: Revision[];
  busyAction: string | null;
  onDownload: (blobId: string, filename: string) => void;
}) {
  const files = revisions
    .flatMap((revision) =>
      revision.representations.map((representation) => ({ revision, representation })),
    )
    .reverse();

  if (!files.length) {
    return <p className="empty-state">No files have been checked in for this Asset yet.</p>;
  }

  return (
    <ul className="representation-list">
      {files.map(({ revision, representation }) => (
        <li key={representation.id}>
          <div>
            <strong>{representation.name}</strong>
            <span>
              R{revision.number} · {representation.media_type}
            </span>
            <small>{representation.blob?.filename ?? "No file attached"}</small>
          </div>
          {representation.blob_id && representation.blob ? (
            <button
              className="secondary-button"
              disabled={busyAction === `download-${representation.blob_id}`}
              onClick={() =>
                onDownload(
                  representation.blob_id as string,
                  representation.blob?.filename ?? `${representation.name}.bin`,
                )
              }
              type="button"
            >
              <Download aria-hidden="true" />{" "}
              {busyAction === `download-${representation.blob_id}` ? "Downloading…" : "Download"}
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function AssetDetailPanel({
  assetDetail,
  busyAction,
  onCancelTransfer,
  onCheckInFormOpenChange,
  onClose,
  onDiscardTransfer,
  onOpenCheckIn,
  onOpenFullPage,
  onRetryCheckin,
  onSubmitUpload,
  onUpdateStatus,
  onUploadCommentChange,
  onUploadFileChange,
  onUploadRepresentationNameChange,
  presentation = "overlay",
  selectedAssetId,
  showCheckInForm,
  transfer,
  uploadForm,
  ...sectionProps
}: AssetDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<AssetDetailTab>("overview");
  const isOpen = Boolean(selectedAssetId && assetDetail.data);
  const collaborationState = sectionProps.collaborationState;
  const asset = assetDetail.data;

  const lockState = collaborationState.data;
  const heldByYou = lockState?.can_checkin ?? false; // owner + healthy lock
  const canReleaseLock = lockState?.can_unlock ?? false;

  const revisions = asset ? [...asset.revisions].sort((a, b) => a.number - b.number) : [];
  const latestRevision = revisions.at(-1);
  const latestFile = latestRevision?.representations.find(
    (representation) => representation.blob_id && representation.blob,
  );

  function lockPill(): ReactNode {
    if (!lockState) return null;
    if (lockState.state === "stale_lock") {
      return <span className="status-pill asset-detail__lock is-stale">Stale lock</span>;
    }
    if (lockState.state === "locked" && heldByYou) {
      return (
        <span className="status-pill asset-detail__lock is-mine">
          <Lock aria-hidden="true" /> Checked out by you
        </span>
      );
    }
    if (lockState.state === "locked") {
      return <span className="status-pill asset-detail__lock">Locked</span>;
    }
    return <span className="status-pill asset-detail__lock">Available</span>;
  }

  const content: ReactNode = asset ? (
    <>
      <div className="asset-detail__statusbar">
        {lockPill()}
        {lockState?.lock ? (
          <span className="asset-detail__meta">
            {(() => {
              const relative = formatRelativeTime(lockState.lock.created_at);
              return relative === "just now"
                ? "checked out just now"
                : `checked out ${relative} ago`;
            })()}
          </span>
        ) : null}
        <span className="asset-detail__statusbar-actions">
          <button
            aria-label="Open as full page"
            className="icon-button"
            onClick={onOpenFullPage}
            type="button"
          >
            <Maximize2 />
          </button>
          <button
            aria-label="Close Asset detail"
            className="icon-button close-detail-button"
            onClick={onClose}
            type="button"
          >
            <X />
          </button>
        </span>
      </div>

      <div className="asset-detail__title">
        <div>
          <h2>{asset.name}</h2>
          <p className="muted-text">
            {asset.description || "No description"} · Revision {latestRevision?.number ?? 0} ·{" "}
            {asset.status}
          </p>
        </div>
        <label>
          <span className="sr-only">Asset status</span>
          <select
            className="status-pill status-pill-select"
            disabled={busyAction === "update-status"}
            onChange={(event) => onUpdateStatus(event.target.value as AssetStatus)}
            value={asset.status}
          >
            {ASSET_STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="asset-detail__actions">
        {heldByYou ? (
          <button className="primary-button" onClick={onOpenCheckIn} type="button">
            <Upload aria-hidden="true" /> Check in
          </button>
        ) : (
          <button
            className="primary-button"
            disabled={busyAction === "checkout" || lockState?.state === "locked"}
            onClick={() => sectionProps.onCheckout()}
            type="button"
          >
            {busyAction === "checkout" ? "Checking out…" : "Check out"}
          </button>
        )}
        <button
          aria-label="Download the latest revision"
          className="secondary-button"
          disabled={!latestFile || busyAction === `download-${latestFile?.blob_id}`}
          onClick={() =>
            latestFile &&
            sectionProps.onDownload(
              latestFile.blob_id as string,
              latestFile.blob?.filename ?? `${asset.name}.bin`,
            )
          }
          type="button"
        >
          <Download aria-hidden="true" />{" "}
          {latestRevision ? `Download R${latestRevision.number}` : "Download"}
        </button>
        <button className="secondary-button" onClick={() => setActiveTab("graph")} type="button">
          <Share2 aria-hidden="true" /> Relationship
        </button>
        {heldByYou ? (
          <button
            className="secondary-button"
            disabled={!canReleaseLock || busyAction === "unlock"}
            onClick={() => sectionProps.onUnlock(false)}
            type="button"
          >
            {busyAction === "unlock" ? "Releasing…" : "Release lock"}
          </button>
        ) : (
          <button className="secondary-button" onClick={onOpenCheckIn} type="button">
            <Upload aria-hidden="true" /> Check in
          </button>
        )}
      </div>

      <AssetDetailTabs onValueChange={setActiveTab} value={activeTab} />

      {activeTab === "overview" ? (
        <>
          <AssetOverview
            asset={asset}
            busyAction={busyAction}
            describeActor={sectionProps.describeActor}
            history={sectionProps.assetHistory}
            metadata={sectionProps.assetMetadata}
            onDownload={sectionProps.onDownload}
          />
          <MetadataAnalysisSection
            busyAction={busyAction}
            selectedAssetId={selectedAssetId}
            {...sectionProps}
          />
        </>
      ) : null}
      {activeTab === "graph" ? (
        <RelationshipsGraphSection
          {...sectionProps}
          busyAction={busyAction}
          selectedAssetId={selectedAssetId}
        />
      ) : null}
      {activeTab === "history" ? (
        <HistoryCollaborationSection busyAction={busyAction} {...sectionProps} />
      ) : null}
      {activeTab === "files" ? (
        <FilesTab
          busyAction={busyAction}
          onDownload={sectionProps.onDownload}
          revisions={revisions}
        />
      ) : null}

      <Dialog
        description="Upload a new file for this Asset while you hold the collaboration lock."
        onOpenChange={onCheckInFormOpenChange}
        open={showCheckInForm}
        title="Check in a new Revision"
      >
        <form className="form-grid compact-form" onSubmit={onSubmitUpload}>
          <label>
            Revision comment
            <input
              disabled={busyAction === "upload"}
              required
              value={uploadForm.comment}
              onChange={(event) => onUploadCommentChange(event.target.value)}
            />
          </label>
          <label>
            Representation name
            <input
              disabled={busyAction === "upload"}
              value={uploadForm.representationName}
              onChange={(event) => onUploadRepresentationNameChange(event.target.value)}
            />
          </label>
          <label>
            File
            <input
              disabled={busyAction === "upload"}
              required
              type="file"
              onChange={(event) => onUploadFileChange(event.target.files?.[0] ?? null)}
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
          <TransferStatus
            phase={transfer.phase === "idle" && !collaborationState.data?.can_checkin ? "permission" : transfer.phase}
            receivedBytes={transfer.receivedBytes}
            totalBytes={transfer.totalBytes}
            message={transfer.message}
            onCancel={() => onCancelTransfer()}
            onRetry={onRetryCheckin}
            onDiscard={() => onDiscardTransfer()}
            retryLabel={transfer.blob ? "Retry check-in" : "Retry transfer"}
          />
        </form>
      </Dialog>
    </>
  ) : null;

  if (presentation === "dock") {
    // A persistent side column: only mounted while an Asset is selected. No portal,
    // no overlay — the table behind it stays fully interactive.
    if (!isOpen || !asset) {
      return null;
    }
    return (
      <aside aria-label={`Asset detail: ${asset.name}`} className="asset-detail-sheet is-docked">
        {content}
      </aside>
    );
  }

  return (
    <DialogPrimitive.Root onOpenChange={(open) => { if (!open) onClose(); }} open={isOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay" />
        <DialogPrimitive.Content className="asset-detail-sheet">
          {asset ? (
            <>
              <DialogPrimitive.Title className="sr-only">{asset.name}</DialogPrimitive.Title>
              <DialogPrimitive.Description className="sr-only">
                Asset details, metadata, relationships and history for {asset.name}.
              </DialogPrimitive.Description>
              {content}
            </>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
