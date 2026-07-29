# FreeCAD Phase 5 Fixtures

These fixtures are copied from the local FreeCAD 1.0 installation at
`C:\Program Files\FreeCAD 1.0\data\examples` for the Phase 5 Official Plugin
vertical slice.

* `native/` contains `.FCStd` source documents used by parser, metadata, and
  dependency-extraction tests.
* `step/` contains a STEP interchange example. The first slice documents it
  as an import/export boundary and does not parse it.

The fixture manifest introduced with the plugin will identify which native
documents are used for each deterministic test. Do not treat a fixture name,
FreeCAD object type, or CAD-specific property as Platform Core vocabulary.
