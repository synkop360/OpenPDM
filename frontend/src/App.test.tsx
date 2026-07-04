import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("shows the OpenPDM foundation shell", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          name: "OpenPDM",
          version: "0.0.0",
          phase: "Foundation",
          architecture: "Modular Monolith"
        })
      })
    );

    render(<App />);

    expect(await screen.findByRole("heading", { name: "OpenPDM" })).toBeInTheDocument();
    expect(await screen.findByText("Modular Monolith")).toBeInTheDocument();
    expect(screen.getAllByText("Foundation")).toHaveLength(2);
  });
});
