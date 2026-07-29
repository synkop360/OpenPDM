# FreeCAD Mechanical Official Plugin Design

**Status:** Approved for implementation planning

**Decision date:** 2026-07-29

## Goal

Prove the Extension API with one useful FreeCAD mechanical workflow while
keeping every FreeCAD-specific definition, parser, metadata key, and
dependency interpretation in an Official Plugin.

## Selected Scope

The first Phase 5 slice analyzes an already stored `.FCStd` Representation.
The `org.openpdm.freecad` Official Plugin will parse FreeCAD's document format
inside the existing WebAssembly sandbox, return plugin-owned metadata, and
report dependency findings through generic Platform Core records.

The slice uses the copied fixtures in `sample/freecad/native/`, with
`AssemblyExample.FCStd` as the in-document dependency fixture and the
remaining files as parser-coverage fixtures. `sample/freecad/step/Schenkel.stp`
is retained to document the interchange boundary only; it is not parsed,
converted, or previewed in this slice.

## Explicit Non-Goals

* No FreeCAD, `FreeCADCmd`, or other third-party executable is launched by the
  Web UI, backend, plugin runtime, or tests.
* No desktop integration is implemented. Desktop-triggered CAD workflows are
  a later feature and require their own design and ADR review.
* No CAD type, assembly rule, BOM field, FreeCAD property, or vendor-specific
  lifecycle concept is added to the Platform Core, Platform Modules, public
  application API vocabulary, or Web UI copy.
* No geometry conversion, preview generation, STEP parsing, BOM extraction,
  native-file mutation, or automatic Asset creation is included.
* The Platform Core does not resolve file paths, infer engineering intent, or
  select relationship types from FreeCAD data.

## Alternatives Considered

### 1. Headless FreeCAD automation

Rejected for this slice. It introduces an external-process boundary, local
installation requirements, and operational behavior that belongs to a future
desktop workflow rather than the browser or backend.

### 2. Embed FreeCAD semantics in a Platform Module

Rejected. It violates the domain-agnostic Platform Core and would make a
vendor integration a privileged built-in capability.

### 3. Sandboxed plugin parser with generic analysis contracts

Selected. The plugin parses an `.FCStd` archive using only bundled code and
the Python standard library available to its WebAssembly Component. The
Platform Core supplies an authorized binary input and persists only generic
metadata, references, and relationships after contract validation.

## Architecture

```text
Stored Representation + authorized actor context
        |
        v
Generic analysis invocation through Extension API
        |
        v
FreeCAD Official Plugin (WASM sandbox)
  - reads bounded `.FCStd` bytes
  - parses FreeCAD archive/XML
  - owns FreeCAD keys and dependency rules
        |
        v
Generic metadata / reference / relationship contributions
        |
        v
Owning Platform Modules validate, authorize, persist, audit, and emit events
```

The plugin must only receive the explicitly requested Representation and the
actor, Organization, and Project context that the Platform Core has
authorized. It receives no database session, repository, storage credential,
package path, or direct Platform Module interface.

### Generic Extension API additions

Two additive Extension API v1 capabilities are necessary before the plugin
can perform the selected workflow. They need ADRs before implementation:

1. A read-only analysis-input contract that allows a running provider to read
   one explicitly requested Representation's bounded bytes after the Platform
   Core authorizes access through the owning Assets and Blobs Platform Modules.
   The contract carries generic content identity, file name, media type, size,
   and bytes; it contains no CAD interpretation and must define a strict size
   limit and rejection behavior.
2. An analysis-contribution contract that permits a provider to return generic
   Metadata Contributions, unresolved Reference Contributions, and
   Asset-to-Asset Relationship Contributions. The plugin supplies the
   contribution values; the owning Metadata and Relationships Platform Modules
   validate authorization, target scope, duplicates, generic shape, audit
   records, and domain events. The Platform Core never infers a relationship
   from a file or interprets a plugin-owned key.

ADR-0036 permits additive Extension API v1 behavior. ADR-0039 must be
extended by a new ADR because its initial capability set does not include
binary analysis or link contributions. The decision must preserve ADR-0031's
distinction: unmapped plugin-extracted dependency identifiers become generic
References; only a caller-supplied mapping to an existing authorized
Engineering Asset can produce a generic Relationship.

### FreeCAD Plugin behavior

The plugin package is an Official Plugin and declares only the new generic
analysis capability plus any existing capability it actually uses. It contains:

* an archive/XML reader for `.FCStd` documents;
* a strict file-signature and archive-layout validator;
* a bounded parser that rejects malformed, encrypted, oversized, or unsupported
  archives with a structured non-retryable Extension API error;
* plugin-owned metadata such as the document label, FreeCAD file format/version
  when present, and deterministic object/link counts;
* plugin-owned rules that identify document links or external file links and
  return unresolved generic References using plugin-owned target URIs;
* relationship contributions only for a caller-supplied, authorized mapping of
  an extracted dependency identifier to an existing Engineering Asset.

The plugin must produce a stable ordering and stable keys for the same input.
It must not fabricate Assets, infer mappings from file names, or depend on
another plugin.

### Application surfaces

The existing plugin administration, provider discovery, generic metadata,
relationship, reference, audit, and event surfaces remain the only application
surfaces. Any Phase 5 invocation UI is generic: it selects an existing
Representation and submits optional explicit Asset mappings. It may show
provider-returned text and normal Platform Core records, but it may not embed
plugin executable UI or launch an executable.

Desktop-only CAD launch, export, and synchronization behavior remains outside
this Phase 5 slice.

## Fixture and Documentation Policy

`sample/freecad/README.md` records the fixture origin and organization. The
plugin test suite will maintain a manifest describing each fixture's expected
metadata and links, with SHA-256 checksums to detect accidental replacement.
For `AssemblyExample.FCStd`, this includes its in-document link identifiers;
an explicit user mapping is required before any becomes an Asset relationship.
The user documentation will state FreeCAD's supported first-slice format, the
analysis size limit, expected metadata/reference/relationship results, known
exclusions, and the fact that no CAD executable is launched.

## Quality Gates

* Contract tests prove non-FreeCAD behavior is absent from the Extension API.
* Plugin unit tests cover valid documents, malformed archives, unsupported
  inputs, deterministic output, and size-limit failures without launching
  FreeCAD.
* Backend integration tests install the Official Plugin through the public
  administration API, invoke it against a stored fixture, and verify generic
  metadata, references, relationships, audit records, and events.
* Web UI tests exercise only generic provider discovery/invocation and record
  rendering; they assert no executable-launch action exists.
* Documentation validation and the established backend/frontend quality gates
  remain required.

## Upgrade Path

After this slice is demonstrably usable, later work may add a desktop-only
FreeCAD integration, richer native metadata, BOM extraction, and explicit
import/export support. Each expansion needs a separate ADR when it changes an
Extension API contract, process boundary, authorization model, or Platform
Core responsibility.
