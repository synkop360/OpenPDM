import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InlineAlert } from "./InlineAlert";

describe("InlineAlert", () => {
  it("announces recoverable feedback as a status", () => {
    render(<InlineAlert tone="success">Asset saved.</InlineAlert>);
    expect(screen.getByRole("status")).toHaveTextContent("Asset saved.");
  });

  it("announces dangerous feedback immediately", () => {
    render(<InlineAlert tone="danger">Upload failed.</InlineAlert>);
    expect(screen.getByRole("alert")).toHaveTextContent("Upload failed.");
  });
});
