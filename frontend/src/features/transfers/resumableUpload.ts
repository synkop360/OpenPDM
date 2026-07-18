import {
  ApiError,
  cancelBlobUploadSession,
  completeBlobUploadSession,
  createBlobUploadSession,
  getBlobUploadSession,
  putBlobUploadChunk,
  type BlobUploadSession,
  type CreateBlobUploadSessionPayload,
} from "../../api";

export type TransferRecovery = {
  sessionId: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  fileLastModified: number;
};

export type ResumableUploadApi = {
  createSession(token: string, payload: CreateBlobUploadSessionPayload, signal?: AbortSignal): Promise<BlobUploadSession>;
  getSession(token: string, sessionId: string, signal?: AbortSignal): Promise<BlobUploadSession>;
  putChunk(token: string, sessionId: string, chunkNumber: number, content: Blob, signal?: AbortSignal): Promise<BlobUploadSession>;
  completeSession(token: string, sessionId: string, signal?: AbortSignal): Promise<BlobUploadSession>;
  cancelSession(token: string, sessionId: string): Promise<void>;
};

const defaultApi: ResumableUploadApi = {
  createSession: createBlobUploadSession,
  getSession: getBlobUploadSession,
  putChunk: putBlobUploadChunk,
  completeSession: completeBlobUploadSession,
  cancelSession: cancelBlobUploadSession,
};

const recoveryKey = (assetId: string) => `openpdm.transfer.${assetId}`;

function identity(file: File): Omit<TransferRecovery, "sessionId"> {
  return { fileName: file.name, fileSize: file.size, fileType: file.type, fileLastModified: file.lastModified };
}

export function saveTransferRecovery(assetId: string, sessionId: string, file: File): TransferRecovery {
  const recovery = { sessionId, ...identity(file) };
  window.sessionStorage.setItem(recoveryKey(assetId), JSON.stringify(recovery));
  return recovery;
}

export function loadTransferRecovery(assetId: string, file?: File): TransferRecovery | null {
  const raw = window.sessionStorage.getItem(recoveryKey(assetId));
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as TransferRecovery;
    if (!/^[A-Za-z0-9_-]{1,128}$/.test(value.sessionId) || typeof value.fileName !== "string" ||
        !value.fileName || typeof value.fileType !== "string" || !Number.isFinite(value.fileSize) ||
        value.fileSize < 0 || !Number.isFinite(value.fileLastModified)) return null;
    if (file) {
      const expected = identity(file);
      if (value.fileName !== expected.fileName || value.fileSize !== expected.fileSize ||
          value.fileType !== expected.fileType || value.fileLastModified !== expected.fileLastModified) return null;
    }
    return value;
  } catch {
    return null;
  }
}

export function clearTransferRecovery(assetId: string): void {
  window.sessionStorage.removeItem(recoveryKey(assetId));
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Transfer cancelled.", "AbortError");
}

async function putChunkWithRetry(
  api: ResumableUploadApi, token: string, sessionId: string, number: number, content: Blob,
  signal?: AbortSignal,
): Promise<BlobUploadSession> {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    throwIfAborted(signal);
    try {
      return await api.putChunk(token, sessionId, number, content, signal);
    } catch (error) {
      if (error instanceof ApiError || attempt === 3) throw error;
    }
  }
  throw new Error("Chunk upload failed.");
}

export async function resumableUpload(options: {
  token: string;
  assetId: string;
  file: File;
  recovery?: TransferRecovery | null;
  api?: ResumableUploadApi;
  signal?: AbortSignal;
  onProgress?: (receivedBytes: number, totalBytes: number) => void;
  onVerifying?: () => void;
}): Promise<BlobUploadSession> {
  const api = options.api ?? defaultApi;
  if (options.file.size === 0) throw new Error("Choose a non-empty file before starting check-in.");
  throwIfAborted(options.signal);
  let current = options.recovery
    ? await api.getSession(options.token, options.recovery.sessionId, options.signal)
    : await api.createSession(options.token, {
        filename: options.file.name,
        media_type: options.file.type || "application/octet-stream",
        total_size_bytes: options.file.size,
      }, options.signal);
  saveTransferRecovery(options.assetId, current.id, options.file);
  options.onProgress?.(current.received_bytes, current.total_size_bytes);

  const totalChunks = Math.ceil(current.total_size_bytes / current.chunk_size_bytes);
  const received = new Set(current.received_chunk_numbers);
  for (let number = 0; number < totalChunks; number += 1) {
    if (received.has(number)) continue;
    const start = number * current.chunk_size_bytes;
    current = await putChunkWithRetry(
      api, options.token, current.id, number,
      options.file.slice(start, Math.min(start + current.chunk_size_bytes, options.file.size)),
      options.signal,
    );
    options.onProgress?.(current.received_bytes, current.total_size_bytes);
  }
  throwIfAborted(options.signal);
  options.onVerifying?.();
  current = await api.completeSession(options.token, current.id, options.signal);
  if (!current.blob) throw new Error("The transfer completed without a Blob result.");
  clearTransferRecovery(options.assetId);
  return current;
}
