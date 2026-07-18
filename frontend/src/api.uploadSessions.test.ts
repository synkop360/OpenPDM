import { afterEach, describe, expect, it, vi } from "vitest";

import {
  cancelBlobUploadSession,
  completeBlobUploadSession,
  createBlobUploadSession,
  getBlobUploadSession,
  putBlobUploadChunk,
} from "./api";

describe("Blob upload-session API", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses the public resumable upload endpoints with typed payloads", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ id: "s" }), {
        status: 200, headers: { "Content-Type": "application/json" },
      }));
    await createBlobUploadSession("token", { asset_id: "asset-1", filename: "a.step", media_type: "application/step", total_size_bytes: 4 });
    await getBlobUploadSession("token", "s");
    await putBlobUploadChunk("token", "s", 0, new Blob(["data"]));
    await completeBlobUploadSession("token", "s");
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await cancelBlobUploadSession("token", "s");

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method ?? "GET"]))
      .toEqual([["/blobs/upload-sessions", "POST"], ["/blobs/upload-sessions/s", "GET"],
        ["/blobs/upload-sessions/s/chunks/0", "PUT"], ["/blobs/upload-sessions/s/complete", "POST"],
        ["/blobs/upload-sessions/s", "DELETE"]]);
  });

  it("forwards an AbortSignal to an in-flight chunk request", async () => {
    const controller = new AbortController();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ id: "s" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await putBlobUploadChunk("token", "s", 0, new Blob(["data"]), controller.signal);
    expect(fetchMock.mock.calls[0][1]?.signal).toBe(controller.signal);
  });
});
