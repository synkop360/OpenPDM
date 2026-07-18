export type LoadableStatus = "idle" | "loading" | "ready" | "error";

export type Loadable<T> = {
  status: LoadableStatus;
  data: T;
  error: string | null;
};

export function createLoadable<T>(data: T): Loadable<T> {
  return { status: "idle", data, error: null };
}
