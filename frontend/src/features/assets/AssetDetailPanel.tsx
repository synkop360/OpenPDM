import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { formatTimestamp } from "../../app/format";
import type { Loadable } from "../../app/loadable";
import type { Asset } from "../../api";
import { AssetDetailTabs, type AssetDetailTab } from "./AssetDetailTabs";
import { MetadataAnalysisSection, type MetadataAnalysisSectionProps } from "./MetadataAnalysisSection";
import { RelationshipsGraphSection, type RelationshipsGraphSectionProps } from "./RelationshipsGraphSection";
import { HistoryCollaborationSection, type HistoryCollaborationSectionProps } from "./HistoryCollaborationSection";

type AssetDetailPanelProps = MetadataAnalysisSectionProps &
  RelationshipsGraphSectionProps &
  HistoryCollaborationSectionProps & {
    assetDetail: Loadable<Asset | null>;
    onClose: () => void;
    selectedAssetId: string | null;
  };

export function AssetDetailPanel({
  assetDetail,
  busyAction,
  onClose,
  selectedAssetId,
  ...sectionProps
}: AssetDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<AssetDetailTab>("metadata");
  const isOpen = Boolean(selectedAssetId && assetDetail.data);

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
                  <span className="status-pill">{assetDetail.data.status}</span>
                </div>
                <p className="muted-text">
                  Created {formatTimestamp(assetDetail.data.created_at)} and updated{" "}
                  {formatTimestamp(assetDetail.data.updated_at)}.
                </p>
              </article>

              <AssetDetailTabs onValueChange={setActiveTab} value={activeTab} />

              {activeTab === "metadata" ? (
                <MetadataAnalysisSection busyAction={busyAction} {...sectionProps} />
              ) : null}
              {activeTab === "relationships" ? <RelationshipsGraphSection {...sectionProps} /> : null}
              {activeTab === "history" ? (
                <HistoryCollaborationSection busyAction={busyAction} {...sectionProps} />
              ) : null}
            </>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
