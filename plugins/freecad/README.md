# FreeCAD Analysis Official Plugin

This Official Plugin provides the first Phase 5 FreeCAD analysis vertical slice.
It receives one authorized, bounded `.FCStd` Representation through the Extension
API `analysis_provider` capability and produces generic OpenPDM contributions.

The plugin parses `Document.xml` from the `.FCStd` ZIP archive using only Python
standard-library archive and XML parsing. It does not import FreeCAD, run
FreeCADCmd, launch any executable, access storage, or inspect a local document
path.

For each supported document, it contributes these plugin-owned metadata keys:

* `freecad.document.label`
* `freecad.document.object_count`
* `freecad.document.link_count`

Each unmapped `App::Link` becomes a plugin-owned `freecad://` Reference. A link
becomes a generic `depends_on` Relationship only when the caller explicitly maps
its stable contribution key (`document.link.<link-name>`) to an existing authorized
Engineering Asset. The Platform Core
does not interpret FreeCAD object types, metadata keys, reference URIs, or the
relationship choice.

## Fixtures

`fixtures.json` records SHA-256 digests for the immutable `.FCStd` files copied
from `C:\Program Files\FreeCAD 1.0\data\examples`. Parser tests use
`AssemblyExample.FCStd`, whose expected document label is `AssemblyExample`,
object count is 53, and document-link count is 13.

## Build

```powershell
uv run python scripts/build_freecad_plugin.py --output plugins/freecad/dist/freecad.openpdm-plugin
```

The build invokes only `componentize-py` to produce the sandboxed WebAssembly
Component and validates the resulting immutable OpenPDM package. It does not
start a CAD application or any external analysis program.
