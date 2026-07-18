import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type BlobUploadSession } from "../../api";
import {
  clearTransferRecovery,
  loadTransferRecovery,
  resumableUpload,
  saveTransferRecovery,
} from "./resumableUpload";

const file = new File(["abcdefghij"], "model.step", {
  type: "application/step",
  lastModified: 42,
});

function session(overrides: Partial<BlobUploadSession> = {}): BlobUploadSession {
  return {
    id: "session-1",
    filename: file.name,
    media_type: file.type,
    total_size_bytes: file.size,
    checksum_sha256: null,
    chunk_size_bytes: 4,
    status: "active",
    received_bytes: 4,
    received_chunk_numbers: [0],
    expires_at: "2026-07-19T00:00:00Z",
    created_at: "2026-07-18T00:00:00Z",
    updated_at: "2026-07-18T00:00:00Z",
    blob: null,
    ...overrides,
  };
}

describe("resumableUpload", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("resumes only missing chunks and reports server-confirmed progress", async () => {
    const putChunk = vi.fn().mockResolvedValueOnce(session({
      received_bytes: 8,
      received_chunk_numbers: [0, 1],
    })).mockResolvedValueOnce(session({
      received_bytes: 10,
      received_chunk_numbers: [0, 1, 2],
    }));
    const progress = vi.fn();
    const result = await resumableUpload({
      token: "token", userId: "user-1",
      assetId: "asset-1",
      file,
      recovery: { userId: "user-1", assetId: "asset-1", sessionId: "session-1", fileName: file.name, fileSize: file.size,
        fileType: file.type, fileLastModified: file.lastModified, blobId: null },
      api: {
        createSession: vi.fn(),
        getSession: vi.fn().mockResolvedValue(session()),
        putChunk,
        completeSession: vi.fn().mockResolvedValue(session({ status: "completed", blob: { id: "blob-1" } as never })),
        cancelSession: vi.fn(),
      },
      onProgress: progress,
    });

    expect(putChunk.mock.calls.map((call) => call[2])).toEqual([1, 2]);
    expect(progress.mock.calls.map((call) => call[0])).toEqual([4, 8, 10]);
    expect(result.blob?.id).toBe("blob-1");
    expect(loadTransferRecovery("user-1", "asset-1")?.blobId).toBe("blob-1");
  });

  it("retries network failures up to three total attempts but never retries semantic 4xx", async () => {
    const networkPut = vi.fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValue(session({ chunk_size_bytes: file.size, received_bytes: 10, received_chunk_numbers: [0] }));
    const api = {
      createSession: vi.fn().mockResolvedValue(session({
        chunk_size_bytes: file.size, received_bytes: 0, received_chunk_numbers: [],
      })),
      getSession: vi.fn(), putChunk: networkPut,
      completeSession: vi.fn().mockResolvedValue(session({ chunk_size_bytes: file.size, status: "completed",
        received_bytes: file.size, received_chunk_numbers: [0], blob: { id: "blob-1" } as never })),
      cancelSession: vi.fn(),
    };
    await resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api });
    expect(networkPut).toHaveBeenCalledTimes(3);

    api.putChunk = vi.fn().mockRejectedValue(new ApiError("conflict", 409));
    await expect(resumableUpload({ token: "token", userId: "user-1", assetId: "asset-2", file, api }))
      .rejects.toMatchObject({ status: 409 });
    expect(api.putChunk).toHaveBeenCalledTimes(1);
  });

  it("can retry completion without uploading file chunks again", async () => {
    const api = {
      createSession: vi.fn(), getSession: vi.fn().mockResolvedValue(session({
        received_bytes: file.size, received_chunk_numbers: [0, 1, 2],
      })), putChunk: vi.fn(),
      completeSession: vi.fn().mockResolvedValue(session({ status: "completed", blob: { id: "blob-1" } as never })),
      cancelSession: vi.fn(),
    };
    await resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api,
      recovery: { userId: "user-1", assetId: "asset-1", sessionId: "session-1", fileName: file.name, fileSize: file.size,
        fileType: file.type, fileLastModified: file.lastModified, blobId: null } });
    expect(api.putChunk).not.toHaveBeenCalled();
    expect(api.completeSession).toHaveBeenCalledOnce();
  });

  it("reuses a completed recovered session without uploading or completing again", async () => {
    const completed = session({ status: "completed", received_bytes: file.size,
      received_chunk_numbers: [0, 1, 2], blob: { id: "blob-1" } as never });
    const api = { createSession: vi.fn(), getSession: vi.fn().mockResolvedValue(completed),
      putChunk: vi.fn(), completeSession: vi.fn(), cancelSession: vi.fn() };
    const result = await resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api,
      recovery: { userId: "user-1", assetId: "asset-1", sessionId: "session-1", fileName: file.name,
        fileSize: file.size, fileType: file.type, fileLastModified: file.lastModified, blobId: "blob-1" } });
    expect(result.blob?.id).toBe("blob-1");
    expect(api.putChunk).not.toHaveBeenCalled();
    expect(api.completeSession).not.toHaveBeenCalled();
  });

  it("clears non-resumable recovery and rejects corrupt server session contracts", async () => {
    saveTransferRecovery("user-1", "asset-1", "session-1", file);
    const terminalApi = { createSession: vi.fn(), getSession: vi.fn().mockRejectedValue(new ApiError("gone", 410)),
      putChunk: vi.fn(), completeSession: vi.fn(), cancelSession: vi.fn() };
    await expect(resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api: terminalApi,
      recovery: loadTransferRecovery("user-1", "asset-1") })).rejects.toThrow("cannot be resumed");
    expect(loadTransferRecovery("user-1", "asset-1")).toBeNull();

    saveTransferRecovery("user-1", "asset-1", "session-1", file);
    terminalApi.getSession.mockReset().mockResolvedValueOnce(session({ total_size_bytes: 999 }));
    await expect(resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api: terminalApi,
      recovery: loadTransferRecovery("user-1", "asset-1") })).rejects.toThrow("does not match");
    expect(loadTransferRecovery("user-1", "asset-1")).toBeNull();
  });

  it("does not return a completed Blob when cancellation wins the completion race", async () => {
    let resolveCompletion!: (value: BlobUploadSession) => void;
    const completion = new Promise<BlobUploadSession>((resolve) => { resolveCompletion = resolve; });
    const controller = new AbortController();
    const api = { createSession: vi.fn().mockResolvedValue(session({ received_bytes: file.size,
      received_chunk_numbers: [0, 1, 2] })), getSession: vi.fn(), putChunk: vi.fn(),
      completeSession: vi.fn().mockReturnValue(completion), cancelSession: vi.fn() };
    const transfer = resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api,
      signal: controller.signal });
    await vi.waitFor(() => expect(api.completeSession).toHaveBeenCalledOnce());
    controller.abort();
    resolveCompletion(session({ status: "completed", received_bytes: file.size,
      received_chunk_numbers: [0, 1, 2], blob: { id: "blob-1" } as never }));
    await expect(transfer).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects received byte counts that do not match confirmed chunk indices", async () => {
    saveTransferRecovery("user-1", "asset-1", "session-1", file);
    const api = { createSession: vi.fn(), getSession: vi.fn().mockResolvedValue(session({ received_bytes: 5 })),
      putChunk: vi.fn(), completeSession: vi.fn(), cancelSession: vi.fn() };
    await expect(resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1", file, api,
      recovery: loadTransferRecovery("user-1", "asset-1") })).rejects.toThrow("invalid progress");
  });

  it("stores only safe recovery metadata and requires the exact same file", () => {
    saveTransferRecovery("user-1", "asset-1", "session-1", file);
    expect(loadTransferRecovery("user-1", "asset-1", file)?.sessionId).toBe("session-1");
    expect(loadTransferRecovery("user-2", "asset-1")).toBeNull();
    const wrong = new File(["abcdefghij"], file.name, { type: file.type, lastModified: 99 });
    expect(loadTransferRecovery("user-1", "asset-1", wrong)).toBeNull();
    expect(window.sessionStorage.getItem("openpdm.transfer.user-1.asset-1")).not.toContain("abcdefghij");
    window.sessionStorage.setItem("openpdm.transfer.user-1.asset-1", JSON.stringify({
      sessionId: "../other", fileName: file.name, fileSize: file.size,
      fileType: file.type, fileLastModified: file.lastModified,
    }));
    expect(loadTransferRecovery("user-1", "asset-1")).toBeNull();
    expect(window.sessionStorage.getItem("openpdm.transfer.user-1.asset-1")).toBeNull();
    clearTransferRecovery("user-1", "asset-1");
    expect(loadTransferRecovery("user-1", "asset-1")).toBeNull();
  });

  it("rejects an empty file before creating a session", async () => {
    const createSession = vi.fn();
    await expect(resumableUpload({ token: "token", userId: "user-1", assetId: "asset-1",
      file: new File([], "empty.step"), api: { createSession, getSession: vi.fn(),
        putChunk: vi.fn(), completeSession: vi.fn(), cancelSession: vi.fn() } }))
      .rejects.toThrow("Choose a non-empty file");
    expect(createSession).not.toHaveBeenCalled();
  });
});
