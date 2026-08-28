# Splice CAD Fixtures

`SampleHarness.spliceproject` is a structurally-faithful, anonymized export of a
real wiring-harness project, saved with Splice CAD desktop's native
**Save As** function (not an API dump, not the MCP `get_plan` summary shape).
`.spliceproject` is plain JSON — no binary container, no separate export step
beyond the app's own Save As.

All human-authored free text (node/pin/page labels, BOM `description`,
`manufacturer`, `mpn`, splice `designator`) has been replaced with generic
placeholders (`Component NN`, `Generic connector NN`, `GENERIC-NNNN`,
`Page N`, `SPL-NNN`) and every `bom[].sourcePartId` UUID (a pointer into the
source account's private Splice CAD part library) has been zeroed out. IDs,
positions, pin counts, wire gauge/color, net names, and every structural
relationship (`bomEntryId`, `sourceNodeId`/`targetNodeId`,
`startEndpoint`/`endEndpoint`, `linkPath`, `conductorIds`) are preserved
unchanged, so the fixture's topology and counts are real.

## Structural facts (deterministic parser-test fixture)

* `schemaVersion`: 3
* `splice_kind`: `"project"` — the format discriminator to check first, same
  role as confirming a `.FCStd` is a ZIP with `Document.xml` before parsing.
* `nodes`: 47 (dict keyed by id; fields: `id`, `label`, `name`, `pins[]`,
  `position`, `shape`, `size`, `type`, optional `category`, optional
  `bomEntryId` linking to `bom[].id`)
* `links`: 50 (dict keyed by id; `sourceNodeId`, `targetNodeId` only)
* `conductors`: 52 (dict keyed by id; `netName`, `gauge`, `color`,
  `startEndpoint`/`endEndpoint` as `{nodeId, pinId?}`, `linkPath[]`)
* `conductorSplices`: 9 (dict keyed by id; `branchPointId`, `conductorIds[]`,
  `spliceType`, `designator`)
* `mates`: 12 (list; `id`, `connector1Id`, `connector2Id`, `pinMappings[]` —
  connector-to-connector mating between component instances inside this file;
  internal topology with no cross-Asset meaning, treated the same as
  `conductorSplices`)
* `bom`: 21 entries (`id`, `mpn`, `manufacturer`, `description`, `type`,
  `spec`, optional `sourcePartId`)
* `pages`/`pageOrder`: 2 — purely presentational (schematic sheet grouping),
  not engineering semantics
* `nodePagePositions`, `nodePageSizes`, `nodePageAssignments`,
  `linkPageAssignments`, `viewState`, `images`: layout/render state only — a
  parser should ignore these, the same way the FreeCAD parser ignores GUI-only
  document data

Present in the schema but **empty** on this fixture, so not exercised by any
test built from it: `assemblyRefs`, `assemblies`, `cables`, `signals`,
`nets`, `deviceGroups`, `wireGroups`, `drcDismissals`,
`subassemblyInstances`. Do not build parsing logic for these sections
without a second fixture that actually populates them.

SHA-256 of `native/SampleHarness.spliceproject`:
`302be655f3c553d4555d120f001f47f3cf95f8f1e714131519b8bbf031f5490a`

No license concern: this fixture is the maintainer's own project data,
anonymized before being committed.
