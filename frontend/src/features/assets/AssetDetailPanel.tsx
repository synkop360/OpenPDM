import { useState, type FormEvent } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { Dialog } from "../../components/primitives/Dialog";
import { formatTimestamp } from "../../app/format";
import type { Loadable } from "../../app/loadable";
import type { Asset, BlobRecord } from "../../api";
import { AssetDetailTabs, type AssetDetailTab } from "./AssetDetailTabs";
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

type AssetDetailPanelProps = MetadataAnalysisSectionProps &
  RelationshipsGraphSectionProps &
  HistoryCollaborationSectionProps & {
    assetDetail: Loadable<Asset | null>;
    onCancelTransfer: () => void;
    onCheckInFormOpenChange: (open: boolean) => void;
    onClose: () => void;
    onDiscardTransfer: () => void;
    onOpenCheckIn: () => void;
    onRetryCheckin: () => void;
    onSubmitUpload: (event: FormEvent<HTMLFormElement>) => void;
    onUpdateStatus: (status: AssetStatus) => void;
    onUploadCommentChange: (value: string) => void;
    onUploadFileChange: (file: File | null) => void;
    onUploadRepresentationNameChange: (value: string) => void;
    selectedAssetId: string | null;
    showCheckInForm: boolean;
    transfer: TransferState;
    uploadForm: UploadForm;
  };

export function AssetDetailPanel({
  assetDetail,
  busyAction,
  onCancelTransfer,
  onCheckInFormOpenChange,
  onClose,
  onDiscardTransfer,
  onOpenCheckIn,
  onRetryCheckin,
  onSubmitUpload,
  onUpdateStatus,
  onUploadCommentChange,
  onUploadFileChange,
  onUploadRepresentationNameChange,
  selectedAssetId,
  showCheckInForm,
  transfer,
  uploadForm,
  ...sectionProps
}: AssetDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<AssetDetailTab>("metadata");
  const isOpen = Boolean(selectedAssetId && assetDetail.data);
  const collaborationState = sectionProps.collaborationState;

  return (
    <DialogPrimitive.Root onOpenChange={(open) => { if (!open) onClose(); }} open={isOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay" />
        <DialogPrimitive.Content className="asset-detail-sheet">
          {assetDetail.data ? (
            <>
              <DialogPrimitive.Title className="sr-only">{assetDetail.data.name}</DialogPrimitive.Title>
              <DialogPrimitive.Description className="sr-only">
                Asset details, metadata, relationships and history for {assetDetail.data.name}.
              </DialogPrimitive.Description>

              <header className="panel-header panel-header-compact">
                <DialogPrimitive.Close asChild>
                  <button aria-label="Close Asset detail" className="icon-button close-detail-button" type="button"><X /></button>
                </DialogPrimitive.Close>
              </header>

              <article className="detail-card asset-summary-card">
                <div className="detail-row">
                  <div>
                    <h3>{assetDetail.data.name}</h3>
                    <p>{assetDetail.data.description || "No description."}</p>
                  </div>
                  <label>
                    <span className="sr-only">Asset status</span>
                    <select
                      className="status-pill status-pill-select"
                      disabled={busyAction === "update-status"}
                      onChange={(event) => onUpdateStatus(event.target.value as AssetStatus)}
                      value={assetDetail.data.status}
                    >
                      {ASSET_STATUSES.map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <p className="muted-text">
                  Created {formatTimestamp(assetDetail.data.created_at)} and updated{" "}
                  {formatTimestamp(assetDetail.data.updated_at)}.
                </p>
              </article>

              <div className="asset-action-row">
                <button
                  className="secondary-button"
                  disabled={busyAction === "checkout" || collaborationState.data?.state === "locked"}
                  onClick={() => sectionProps.onCheckout()}
                  type="button"
                >
                  {busyAction === "checkout" ? "Checking out..." : "Check out"}
                </button>
                <button className="secondary-button" onClick={onOpenCheckIn} type="button">
                  Check in
                </button>
                <button
                  className="secondary-button"
                  disabled={busyAction === "unlock" || !collaborationState.data?.can_unlock}
                  onClick={() => sectionProps.onUnlock(false)}
                  type="button"
                >
                  {busyAction === "unlock" ? "Unlocking..." : "Unlock"}
                </button>
              </div>

              <AssetDetailTabs onValueChange={setActiveTab} value={activeTab} />

              {activeTab === "metadata" ? (
                <MetadataAnalysisSection busyAction={busyAction} {...sectionProps} />
              ) : null}
              {activeTab === "relationships" ? <RelationshipsGraphSection {...sectionProps} /> : null}
              {activeTab === "history" ? (
                <HistoryCollaborationSection busyAction={busyAction} {...sectionProps} />
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
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
