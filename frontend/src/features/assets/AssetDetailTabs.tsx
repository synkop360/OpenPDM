export const assetDetailTabs = ["metadata", "relationships", "history"] as const;

export type AssetDetailTab = (typeof assetDetailTabs)[number];

const labels: Record<AssetDetailTab, string> = {
  metadata: "Metadata & Analysis",
  relationships: "Relationships & Graph",
  history: "History & Collaboration",
};

type AssetDetailTabsProps = {
  onValueChange: (value: AssetDetailTab) => void;
  value: AssetDetailTab;
};

export function AssetDetailTabs({ onValueChange, value }: AssetDetailTabsProps) {
  return (
    <nav aria-label="Asset detail sections" className="project-tabs">
      {assetDetailTabs.map((tab) => (
        <button
          aria-current={tab === value ? "page" : undefined}
          className={tab === value ? "project-tab is-active" : "project-tab"}
          key={tab}
          onClick={() => {
            if (tab !== value) onValueChange(tab);
          }}
          type="button"
        >
          {labels[tab]}
        </button>
      ))}
    </nav>
  );
}
