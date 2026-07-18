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
  userId: string;
  assetId: string;
  sessionId: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  fileLastModified: number;
  blobId: string | null;
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

const recoveryKey = (userId: string, assetId: string) => `openpdm.transfer.${userId}.${assetId}`;

export function transferFileIdentity(file: File) {
  return { fileName: file.name, fileSize: file.size, fileType: file.type, fileLastModified: file.lastModified };
}

export function saveTransferRecovery(userId: string, assetId: string, sessionId: string, file: File): TransferRecovery {
  const recovery = { userId, assetId, sessionId, ...transferFileIdentity(file), blobId: null };
  window.sessionStorage.setItem(recoveryKey(userId, assetId), JSON.stringify(recovery));
  return recovery;
}

function saveCompletedRecovery(userId: string, assetId: string, sessionId: string, file: File, blobId: string): void {
  window.sessionStorage.setItem(recoveryKey(userId, assetId), JSON.stringify({
    userId, assetId, sessionId, ...transferFileIdentity(file), blobId,
  } satisfies TransferRecovery));
}

export function loadTransferRecovery(userId: string, assetId: string, file?: File): TransferRecovery | null {
  const raw = window.sessionStorage.getItem(recoveryKey(userId, assetId));
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as TransferRecovery;
    if (value.userId !== userId || value.assetId !== assetId || !/^[A-Za-z0-9_-]{1,128}$/.test(value.sessionId) ||
        typeof value.fileName !== "string" ||
        !value.fileName || typeof value.fileType !== "string" || !Number.isFinite(value.fileSize) ||
        value.fileSize < 0 || !Number.isFinite(value.fileLastModified) ||
        !(value.blobId === null || (typeof value.blobId === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(value.blobId)))) {
      clearTransferRecovery(userId, assetId);
      return null;
    }
    if (file) {
      const expected = transferFileIdentity(file);
      if (value.fileName !== expected.fileName || value.fileSize !== expected.fileSize ||
          value.fileType !== expected.fileType || value.fileLastModified !== expected.fileLastModified) return null;
    }
    return value;
  } catch {
    clearTransferRecovery(userId, assetId);
    return null;
  }
}

export function fileMatchesRecovery(file: File, recovery: TransferRecovery): boolean {
  const expected = transferFileIdentity(file);
  return recovery.fileName === expected.fileName && recovery.fileSize === expected.fileSize &&
    recovery.fileType === expected.fileType && recovery.fileLastModified === expected.fileLastModified;
}

export function canReuseCompletedBlob(
  userId: string, assetId: string, file: File, blobId: string, recovery: TransferRecovery | null,
): boolean {
  return Boolean(recovery && recovery.userId === userId && recovery.assetId === assetId && recovery.blobId === blobId &&
    fileMatchesRecovery(file, recovery));
}

export function clearTransferRecovery(userId: string, assetId: string): void {
  window.sessionStorage.removeItem(recoveryKey(userId, assetId));
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Transfer cancelled.", "AbortError");
}

export class NonResumableTransferError extends Error {
  constructor(message: string) { super(message); this.name = "NonResumableTransferError"; }
}

function validateSession(
  session: BlobUploadSession,
  file: File,
  expected?: { id: string; chunkSize: number },
): BlobUploadSession {
  const mediaType = file.type || "application/octet-stream";
  if (session.filename !== file.name || session.media_type !== mediaType || session.total_size_bytes !== file.size) {
    throw new NonResumableTransferError("The saved upload session does not match the selected file.");
  }
  if (expected && (session.id !== expected.id || session.chunk_size_bytes !== expected.chunkSize)) {
    throw new NonResumableTransferError("The upload session identity changed during transfer.");
  }
  if (!Number.isFinite(session.chunk_size_bytes) || session.chunk_size_bytes <= 0 ||
      !Number.isFinite(session.received_bytes) || session.received_bytes < 0 ||
      session.received_bytes > session.total_size_bytes) {
    throw new NonResumableTransferError("The upload session returned invalid progress data.");
  }
  const totalChunks = Math.ceil(session.total_size_bytes / session.chunk_size_bytes);
  const indices = session.received_chunk_numbers;
  if (new Set(indices).size !== indices.length || indices.some((value) =>
    !Number.isInteger(value) || value < 0 || value >= totalChunks)) {
    throw new NonResumableTransferError("The upload session returned invalid chunk data.");
  }
  const expectedReceivedBytes = indices.reduce((sum, number) => {
    const start = number * session.chunk_size_bytes;
    return sum + Math.min(session.chunk_size_bytes, session.total_size_bytes - start);
  }, 0);
  if (session.received_bytes !== expectedReceivedBytes) {
    throw new NonResumableTransferError("The upload session returned invalid progress data.");
  }
  if ((session.status === "completed") !== Boolean(session.blob)) {
    throw new NonResumableTransferError("The upload session returned an invalid completion state.");
  }
  return session;
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
  userId: string;
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
  let current: BlobUploadSession;
  try {
    current = options.recovery
      ? await api.getSession(options.token, options.recovery.sessionId, options.signal)
      : await api.createSession(options.token, {
        filename: options.file.name,
        media_type: options.file.type || "application/octet-stream",
        total_size_bytes: options.file.size,
      }, options.signal);
    current = validateSession(current, options.file);
    if (options.recovery && current.id !== options.recovery.sessionId) {
      throw new NonResumableTransferError("The saved upload session identity does not match the server response.");
    }
  } catch (error) {
    const terminal = error instanceof NonResumableTransferError ||
      (error instanceof ApiError && [404, 409, 410].includes(error.status));
    if (options.recovery && terminal) {
      clearTransferRecovery(options.userId, options.assetId);
      throw new NonResumableTransferError(
        error instanceof NonResumableTransferError ? error.message : "The saved transfer cannot be resumed. Discard it and start again.",
      );
    }
    throw error;
  }
  saveTransferRecovery(options.userId, options.assetId, current.id, options.file);
  options.onProgress?.(current.received_bytes, current.total_size_bytes);

  if (current.status === "completed") {
    throwIfAborted(options.signal);
    saveCompletedRecovery(options.userId, options.assetId, current.id, options.file, current.blob!.id);
    return current;
  }
  if (current.status !== "active") {
    clearTransferRecovery(options.userId, options.assetId);
    throw new NonResumableTransferError("The saved transfer is no longer active. Discard it and start again.");
  }

  const totalChunks = Math.ceil(current.total_size_bytes / current.chunk_size_bytes);
  const sessionContract = { id: current.id, chunkSize: current.chunk_size_bytes };
  const received = new Set(current.received_chunk_numbers);
  for (let number = 0; number < totalChunks; number += 1) {
    if (received.has(number)) continue;
    const start = number * current.chunk_size_bytes;
    current = await putChunkWithRetry(
      api, options.token, current.id, number,
      options.file.slice(start, Math.min(start + current.chunk_size_bytes, options.file.size)),
      options.signal,
    );
    current = validateSession(current, options.file, sessionContract);
    options.onProgress?.(current.received_bytes, current.total_size_bytes);
  }
  throwIfAborted(options.signal);
  options.onVerifying?.();
  current = await api.completeSession(options.token, current.id, options.signal);
  throwIfAborted(options.signal);
  current = validateSession(current, options.file, sessionContract);
  if (!current.blob) throw new Error("The transfer completed without a Blob result.");
  saveCompletedRecovery(options.userId, options.assetId, current.id, options.file, current.blob.id);
  return current;
}
