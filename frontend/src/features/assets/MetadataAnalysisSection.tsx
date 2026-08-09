import { InlineAlert } from "../../components/feedback/InlineAlert";
import { describeMetadataEntry } from "../../app/provenance";
import type { Loadable } from "../../app/loadable";
import type {
  AnalysisResult,
  MetadataEntry,
  ProviderDescriptor,
  ProviderOptionSet,
  Representation,
  Revision,
} from "../../api";

type AnalysisRepresentationOption = {
  representation: Representation;
  revision: Revision;
};

export type MetadataAnalysisSectionProps = {
  analysisBusy: boolean;
  analysisRepresentations: AnalysisRepresentationOption[];
  analysisResult: AnalysisResult | null;
  assetMetadata: Loadable<MetadataEntry[]>;
  busyAction: string | null;
  onAnalysisRepresentationChange: (representationId: string) => void;
  onApplyMetadataProvider: (provider: ProviderDescriptor) => void;
  onInvokeAnalysisProvider: (provider: ProviderDescriptor) => void;
  onProviderSelectionChange: (providerId: string, value: string) => void;
  providerOptions: Record<string, ProviderOptionSet[]>;
  providers: Loadable<ProviderDescriptor[]>;
  providerSelections: Record<string, string>;
  selectedAnalysisRepresentation: Representation | null;
};

export function MetadataAnalysisSection({
  analysisBusy,
  analysisRepresentations,
  analysisResult,
  assetMetadata,
  busyAction,
  onAnalysisRepresentationChange,
  onApplyMetadataProvider,
  onInvokeAnalysisProvider,
  onProviderSelectionChange,
  providerOptions,
  providers,
  providerSelections,
  selectedAnalysisRepresentation,
}: MetadataAnalysisSectionProps) {
  return (
    <>
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
                    onChange={(event) => onProviderSelectionChange(provider.id, event.target.value)}
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
                onClick={() => onApplyMetadataProvider(provider)}
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
          providers.status === "error" ? (
            <InlineAlert tone="danger">{providers.error}</InlineAlert>
          ) : (
            <p className="empty-state">No running Metadata Provider is available.</p>
          )
        ) : null}

        {assetMetadata.data.length > 0 ? (
          <div className="metadata-list">
            {assetMetadata.data.map((entry) => (
              <div key={entry.id}>
                <p>{describeMetadataEntry(entry)}</p>
                <details className="manifest-review">
                  <summary>Technical details</summary>
                  <dl>
                    <div>
                      <dt>Key</dt>
                      <dd><code>{entry.key}</code></dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd><code>{entry.source}</code></dd>
                    </div>
                    <div>
                      <dt>Value type</dt>
                      <dd><code>{entry.value_type}</code></dd>
                    </div>
                  </dl>
                </details>
              </div>
            ))}
          </div>
        ) : null}
      </article>

      {providers.data.some((provider) =>
        provider.capabilities.includes("analysis_provider"),
      ) ? (
        <article className="detail-card provider-card">
          <div className="detail-row">
            <div>
              <h3>Representation analysis</h3>
              <p>Run a discovered provider against one existing Representation.</p>
            </div>
            {analysisResult ? (
              <span className="status-pill">
                {analysisResult.metadata.length + analysisResult.references.length + analysisResult.relationships.length} results
              </span>
            ) : null}
          </div>

          <label>
            Representation to analyze
            <select
              disabled={analysisRepresentations.length === 0 || analysisBusy}
              value={selectedAnalysisRepresentation?.id ?? ""}
              onChange={(event) => onAnalysisRepresentationChange(event.target.value)}
            >
              {analysisRepresentations.map(({ representation, revision }) => (
                <option key={representation.id} value={representation.id}>
                  {representation.name} - Revision {revision.number}
                </option>
              ))}
            </select>
          </label>

          {providers.data.filter((provider) =>
            provider.capabilities.includes("analysis_provider"),
          ).map((provider) => (
            <div className="provider-control" key={provider.id}>
              <div>
                <strong>{provider.name}</strong>
                <small>{provider.id}</small>
              </div>
              <button
                className="secondary-button"
                disabled={
                  !selectedAnalysisRepresentation ||
                  analysisBusy
                }
                onClick={() => onInvokeAnalysisProvider(provider)}
                type="button"
              >
                {busyAction === `provider-analysis-${provider.id}`
                  ? "Analyzing..."
                  : "Analyze representation"}
              </button>
            </div>
          ))}

          {analysisRepresentations.length === 0 ? (
            <p className="empty-state">No Representation is available for analysis yet.</p>
          ) : null}
          {analysisResult ? (
            <p className="muted-text" role="status">
              Analysis complete: {analysisResult.metadata.length} metadata, {analysisResult.references.length} references, {analysisResult.relationships.length} relationships.
            </p>
          ) : null}
        </article>
      ) : null}
    </>
  );
}
