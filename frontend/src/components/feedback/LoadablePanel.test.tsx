import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoadablePanel } from "./LoadablePanel";

describe("LoadablePanel", () => {
  it("exposes progress without replacing the workspace", () => {
    render(
      <LoadablePanel label="assets" state={{ status: "loading", data: [], error: null }}>
        {() => null}
      </LoadablePanel>,
    );
    expect(screen.getByLabelText("Loading assets")).toHaveAttribute("aria-busy", "true");
  });

  it("offers a scoped retry action", () => {
    const onRetry = vi.fn();
    render(
      <LoadablePanel
        label="assets"
        onRetry={onRetry}
        state={{ status: "error", data: [], error: "Network unavailable" }}
      >
        {() => null}
      </LoadablePanel>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
