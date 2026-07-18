import { describe, expect, it } from "vitest";

import { canReuseCompletedBlob, type TransferRecovery } from "./resumableUpload";

const file = new File(["part"], "part.step", { type: "application/step", lastModified: 10 });
const recovery: TransferRecovery = { userId: "user-1", assetId: "asset-1", sessionId: "session-1", blobId: "blob-1",
  fileName: file.name, fileSize: file.size, fileType: file.type, fileLastModified: file.lastModified };

describe("check-in transfer lifecycle guard", () => {
  it("never reuses a completed Blob for another Asset or file identity", () => {
    expect(canReuseCompletedBlob("user-1", "asset-1", file, "blob-1", recovery)).toBe(true);
    expect(canReuseCompletedBlob("user-2", "asset-1", file, "blob-1", recovery)).toBe(false);
    expect(canReuseCompletedBlob("user-1", "asset-2", file, "blob-1", recovery)).toBe(false);
    expect(canReuseCompletedBlob("user-1", "asset-1", file, "blob-2", recovery)).toBe(false);
    expect(canReuseCompletedBlob("user-1", "asset-1", new File(["part"], file.name, {
      type: file.type, lastModified: 11,
    }), "blob-1", recovery)).toBe(false);
  });
});
