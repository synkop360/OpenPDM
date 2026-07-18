import type { ReactNode } from "react";
import type { Loadable } from "../../app/loadable";
import { InlineAlert } from "./InlineAlert";

type LoadablePanelProps<T> = {
  children: (data: T) => ReactNode;
  empty?: ReactNode;
  isEmpty?: (data: T) => boolean;
  label: string;
  onRetry?: () => void;
  state: Loadable<T>;
};

export function LoadablePanel<T>({
  children,
  empty = "Nothing to show yet.",
  isEmpty,
  label,
  onRetry,
  state,
}: LoadablePanelProps<T>) {
  if (state.status === "idle" || state.status === "loading") {
    return (
      <div aria-busy="true" aria-label={`Loading ${label}`} className="loadable-skeleton">
        <span />
        <span />
        <span />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <InlineAlert title={`Could not load ${label}`} tone="danger">
        <p>{state.error ?? "An unexpected error occurred."}</p>
        {onRetry ? (
          <button className="secondary-button" onClick={onRetry} type="button">
            Try again
          </button>
        ) : null}
      </InlineAlert>
    );
  }

  if (isEmpty?.(state.data)) {
    return <p className="empty-state">{empty}</p>;
  }

  return children(state.data);
}
