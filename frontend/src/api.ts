export type FoundationStatus = {
  name: string;
  version: string;
  phase: string;
  architecture: string;
};

export async function fetchFoundationStatus(): Promise<FoundationStatus> {
  const response = await fetch("/foundation");
  if (!response.ok) {
    throw new Error(`OpenPDM API request failed with status ${response.status}`);
  }
  return response.json() as Promise<FoundationStatus>;
}
