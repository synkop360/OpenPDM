import { useEffect, useState } from "react";
import { fetchFoundationStatus, type FoundationStatus } from "../api";
import { createLoadable, type Loadable } from "../app/loadable";

export function useFoundationStatus(): Loadable<FoundationStatus | null> {
  const [foundation, setFoundation] = useState<Loadable<FoundationStatus | null>>(
    createLoadable<FoundationStatus | null>(null),
  );

  useEffect(() => {
    setFoundation((current) => ({ ...current, status: "loading", error: null }));
    fetchFoundationStatus()
      .then((result) => setFoundation({ status: "ready", data: result, error: null }))
      .catch((error: unknown) =>
        setFoundation({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "Unknown API error",
        }),
      );
  }, []);

  return foundation;
}
