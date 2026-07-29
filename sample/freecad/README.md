# FreeCAD Phase 5 Fixtures

These fixtures are copied from the local FreeCAD 1.0 installation at
`C:\Program Files\FreeCAD 1.0\data\examples` for the Phase 5 Official Plugin
vertical slice.

* `native/` contains `.FCStd` source documents used by parser, metadata, and
  dependency-extraction tests.
* `step/` contains a STEP interchange example. The first slice documents it
  as an import/export boundary and does not parse it.

The plugin-owned fixture manifest at `plugins/freecad/fixtures.json` records
the SHA-256 digest for every native document. `AssemblyExample.FCStd` is the
deterministic parser fixture: its document label is `AssemblyExample`, its
object count is 53, and it has 13 `App::Link` document links. Do not treat a
fixture name, FreeCAD object type, or CAD-specific property as Platform Core
vocabulary.

The source installation's `doc/LICENSE.html` identifies the FreeCAD application
as LGPL 2 or later. No individual license notice accompanied these example
documents in the copied directory. The repository records provenance and hashes
only; contributors and redistributors must verify the applicable upstream
example-data terms before redistributing the fixtures.
