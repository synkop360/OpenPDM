import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TransferStatus, type TransferPhase } from "./TransferStatus";

describe("TransferStatus", () => {
  it.each<[TransferPhase, string]>([
    ["preparing", "Preparing transfer"], ["uploading", "Uploading file"],
    ["verifying", "Verifying file integrity"], ["checking-in", "Creating immutable Revision"],
    ["failed", "Transfer interrupted"], ["cancelled", "Transfer cancelled"],
    ["awaiting-file", "Resume transfer"], ["success", "Check-in complete"],
    ["permission", "Check-in unavailable"],
  ])("announces the %s state accessibly", (phase, label) => {
    render(<TransferStatus phase={phase} receivedBytes={4} totalBytes={10} />);
    expect(screen.getByRole("status")).toHaveTextContent(label);
  });

  it("exposes semantic progress and available recovery actions", () => {
    const cancel = vi.fn();
    const retry = vi.fn();
    render(<TransferStatus phase="uploading" receivedBytes={4} totalBytes={10} onCancel={cancel} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "4");
    fireEvent.click(screen.getByRole("button", { name: "Cancel transfer" }));
    expect(cancel).toHaveBeenCalledOnce();

    render(<TransferStatus phase="failed" receivedBytes={4} totalBytes={10} onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry check-in" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("offers discard for terminal recovery and never offers cancel during check-in", () => {
    const discard = vi.fn();
    const { rerender } = render(<TransferStatus phase="awaiting-file" receivedBytes={0} totalBytes={10} onDiscard={discard} />);
    fireEvent.click(screen.getByRole("button", { name: "Discard transfer" }));
    expect(discard).toHaveBeenCalledOnce();
    rerender(<TransferStatus phase="checking-in" receivedBytes={10} totalBytes={10}
      onCancel={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Cancel transfer" })).not.toBeInTheDocument();
    rerender(<TransferStatus phase="failed" receivedBytes={10} totalBytes={10} onRetry={vi.fn()}
      retryLabel="Retry transfer" onDiscard={discard} />);
    expect(screen.getByRole("button", { name: "Retry transfer" })).toBeInTheDocument();
  });
});
