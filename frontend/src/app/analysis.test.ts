import { describe, expect, it } from "vitest";
import { isAnalyzableRepresentation } from "./analysis";

describe("isAnalyzableRepresentation", () => {
  it("matches known engineering file extensions, case-insensitively", () => {
    for (const name of [
      "rotor-hub.FCStd",
      "bracket.step",
      "shaft.STP",
      "board.kicad_pcb",
      "panel.stl",
      "tune.msq",
      "assembly.sldasm",
    ]) {
      expect(isAnalyzableRepresentation(name)).toBe(true);
    }
  });

  it("rejects unknown or missing extensions", () => {
    for (const name of ["notes.txt", "native.dat", "archive.zip", "photo.png", "", null, undefined]) {
      expect(isAnalyzableRepresentation(name)).toBe(false);
    }
  });

  it("only matches the trailing extension", () => {
    expect(isAnalyzableRepresentation("step-by-step-guide.pdf")).toBe(false);
    expect(isAnalyzableRepresentation("v2.step.bak")).toBe(false);
  });
});
