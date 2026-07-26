export const SESSION_TOKEN_KEY = "openpdm.sessionToken";
export const ORG_KEY = "openpdm.organizationId";
export const PROJECT_KEY = "openpdm.projectId";
export const ASSET_KEY = "openpdm.assetId";

export function readStoredValue(key: string): string | null {
  return window.localStorage.getItem(key);
}

export function writeStoredValue(key: string, value: string | null): void {
  if (value) {
    window.localStorage.setItem(key, value);
    return;
  }
  window.localStorage.removeItem(key);
}
