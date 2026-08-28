# Splice CAD Analysis Official Plugin

This Official Plugin provides the Splice CAD wiring-harness analysis vertical
slice. It receives one authorized, bounded `.spliceproject` Representation
through the Extension API `analysis_provider` capability and produces generic
OpenPDM contributions. It mirrors the scope of the `org.openpdm.freecad` plugin,
targeting Splice CAD projects instead of FreeCAD `.FCStd` documents.

`.spliceproject` is the plain-JSON file produced by Splice CAD desktop's native
**Save As** button. The plugin parses it with only the Python standard library
(`json.loads`). It never calls the Splice CAD API or bridge, never has network
access, never reads a local file path, and never launches an external process.

For each supported project, it contributes these plugin-owned metadata keys:

* `splicecad.plan.node_count`
* `splicecad.plan.link_count`
* `splicecad.plan.conductor_count`
* `splicecad.plan.conductor_splice_count`
* `splicecad.plan.mate_count`
* `splicecad.plan.bom_count`

Each BOM entry becomes a plugin-owned `splicecad://` Reference. A BOM entry
becomes a generic `depends_on` Relationship only when the caller explicitly maps
its stable contribution key (`bom.<bom-entry-id>`) to an existing authorized
Engineering Asset in the same Project. `bom[].sourcePartId` points into the
source account's private Splice CAD part library, not into OpenPDM; it is
carried only as opaque descriptive metadata on the contribution when present,
never as a Reference or relationship target. The Platform Core does not
interpret Splice CAD node types, metadata keys, reference URIs, or the
relationship choice.

## Fixtures

`fixtures.json` records the SHA-256 digest and deterministic structural facts
for the immutable `sample/splice-cad/native/SampleHarness.spliceproject`
fixture (`schemaVersion` 3, `splice_kind` `project`; 47 nodes, 50 links, 52
conductors, 9 conductor splices, 12 mates, 21 BOM entries). Its provenance and
anonymization are recorded in [the sample README](../../sample/splice-cad/README.md).

## Build

```powershell
uv run python scripts/build_splice_cad_plugin.py --output plugins/splice-cad/dist/splice-cad.openpdm-plugin
```

The build invokes only `componentize-py` to produce the sandboxed WebAssembly
Component and validates the resulting immutable OpenPDM package. It does not
start Splice CAD or any external analysis program.
