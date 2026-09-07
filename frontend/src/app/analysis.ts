/**
 * Representation file extensions an Analysis Provider is expected to understand.
 * When a Representation with one of these lands, the asset detail runs the first
 * discovered analysis provider against it automatically.
 */
export const ANALYZABLE_REPRESENTATION_EXTENSIONS =
  /\.(fcstd|step|stp|iges|igs|stl|3mf|obj|kicad_pcb|kicad_sch|brd|sch|net|sldprt|sldasm|catpart|catproduct|prt|asm|ipt|iam|dwg|dxf|msq)$/i;

/** Whether a Representation's file name looks like something an Analysis Provider handles. */
export function isAnalyzableRepresentation(fileName: string | null | undefined): boolean {
  return (
    typeof fileName === "string" && ANALYZABLE_REPRESENTATION_EXTENSIONS.test(fileName.trim())
  );
}
