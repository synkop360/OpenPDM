# ADR-0051 - Adopt React Flow For The Bounded Asset Graph Visualization

**Status:** Accepted

---

# Context

The Relationships & Graph tab's "Bounded graph summary" card currently shows the result of the existing `getAssetGraph` call as six text tiles (node count, relationship count, direction, max depth, path target, path exists). A reader has to reconstruct the actual shape of the graph from those numbers; there is no visualization of the graph itself, even though the response already carries everything needed to draw one (`nodes: GraphNode[]`, `relationships: Relationship[]`).

ADR-0030 bounds what this graph can ever contain: a default traversal depth of 3, a hard maximum of 10, and an explicit exclusion of graph analytics, shortest-path optimization and centrality calculations. Whatever renders this data must stay inside that bound and must not introduce a new backend call to get there -- the `getAssetGraph` response the Relationships & Graph tab already fetches is the only input.

ADR-0044 adopted React Router, Radix primitives, Lucide icons, repository-owned CSS tokens, Vitest and Playwright as the Web UI's interaction stack, and asked contributors to prefer existing primitives over ad hoc components. None of those primitives cover diagram rendering, so this decision has to weigh two real options rather than default to either extreme:

* build a small, purpose-built SVG diagram directly against the bounded `AssetGraph` shape, with no new dependency and hand-rolled pan/zoom/drag interaction; or
* adopt a graph-rendering library that provides pan, zoom, drag and edge rendering as a maintained component, and lay out the bounded set of nodes and relationships on top of it.

Limiting dependencies does not mean avoiding them at all cost -- ADR-0044 itself asks contributors to prefer an existing, maintained primitive over an ad hoc one when the primitive actually covers the need (as it did for Radix over hand-rolled dialogs and menus). Pan, zoom, drag-to-rearrange and pointer/touch/keyboard interaction for a diagram is exactly that kind of real, non-trivial UI engineering: getting it right (across mouse, touch and keyboard, without introducing accessibility regressions) is significant, ongoing work that a maintained library already does. The question this ADR answers is whether that work is worth taking on as a dependency here, given how small and bounded this graph is by construction.

---

# Decision

OpenPDM will render the Asset Graph using React Flow (published as `@xyflow/react`) instead of a fully hand-rolled SVG diagram.

A new presentational component reads the same `AssetGraph` response the Relationships & Graph tab already fetches (`nodes`, `relationships`, `direction`, `max_depth`, `target_asset_id`, `path_exists`, `has_cycle`) and replaces the six-tile summary card with it. No new API call is introduced; the component does not request depth, direction or traversal behavior beyond what ADR-0030 already bounds and the tab already queries. React Flow does not compute graph layout itself, so OpenPDM still owns a small, deterministic layout function that places the fetched nodes (the selected Asset at the center, related nodes grouped around it by relationship) -- what React Flow owns is rendering those positioned nodes and their connecting edges, and the pan, zoom and drag interaction on top of them.

Nodes use a custom React Flow node type so OpenPDM keeps full control of each node's accessible name and content, built from the Asset's name and status exactly as the rest of the Web UI already labels Assets; nodes remain real DOM elements reachable the same way other interactive Web UI elements are. Clicking a node calls the tab's existing `onSelectAsset` handler exactly like the current "Open asset" buttons do -- no new navigation or authorization path is introduced. Edges are labelled with the relationship type and carry directional arrowheads. `has_cycle` and `path_exists` continue to render as their own status indicators near the diagram rather than being encoded only visually, so that information stays available regardless of how well the diagram itself is read.

React Flow ships as a direct `frontend/package.json` dependency, reviewed and pinned the same way the project's other frontend dependencies are.

---

# Consequences

## Positive

* Pan, zoom and drag-to-rearrange come from a maintained library instead of hand-rolled pointer, touch and keyboard event handling that OpenPDM would otherwise have to build and keep correct itself.
* React Flow renders nodes as real DOM elements with custom node components, so OpenPDM keeps the same level of control over accessible labels and content that a hand-rolled SVG diagram would have had -- adopting the library does not hand accessibility off to a black box.
* The library is actively maintained and widely used for exactly this kind of bounded, node-and-edge diagram, so OpenPDM is not carrying novel-library risk.
* Layout stays OpenPDM's own deterministic function operating on the already-bounded `AssetGraph` response; the library is not asked to do anything beyond ADR-0030's scope.

## Trade-offs

* This adds a new runtime dependency (and its transitive dependencies) to the Web UI's audited surface and bundle size, which ADR-0044's dependency-minimalism precedent means should not be taken lightly -- accepted here because pan/zoom/drag interaction is real complexity worth not re-building, not because the dependency is free.
* React Flow's own accessibility and keyboard-interaction behavior becomes something OpenPDM must verify (via the project's existing axe-core coverage and manual keyboard testing) rather than something fully under OpenPDM's own code, unlike a hand-rolled diagram.
* Drag, pan and zoom interactions are harder to assert against in Playwright than plain static SVG would have been; end-to-end coverage for this component will focus on node/edge content and the click-to-select-Asset path rather than interaction gestures themselves.
* This decision does not scale to graph analytics or large unbounded graphs -- it deliberately only has to work within ADR-0030's existing bound, and would need to be revisited (not extended) if that bound changes.

---

# Alternatives Considered

## Hand-Rolled Bounded SVG Diagram

Rejected. A dependency-free SVG diagram was the initial default given how small and bounded this graph is by construction, but it would require OpenPDM to build and maintain its own pan/zoom/drag interaction handling to give users a comparable ability to explore a diagram, rather than a static, cramped one. That is exactly the kind of already-solved interaction-engineering problem ADR-0044 asks contributors to prefer a maintained primitive for, once a suitable one exists -- which React Flow does for diagrams the way Radix does for dialogs and menus.

## Adopt `vis-network`

Rejected because it renders to `<canvas>`, which is opaque to Playwright's DOM-based assertions and to screen readers, and it is a general-purpose network visualization library sized for graphs well beyond ADR-0030's bounded traversal scope. Adopting it would mean carrying a dependency whose main strengths -- large-graph performance and physics-based layout -- this project's bounded graph will never exercise, while giving up the DOM-node accessibility control React Flow's custom nodes preserve.

## Extend the existing six-tile summary instead of visualizing

Rejected because it does not address the actual problem: a reader still cannot see the graph's shape, only counts describing it. The issue this ADR resolves specifically asks for a visualization built from data the tab already has, not a richer summary of the same non-visual kind.

---

# References

* ADR-0030 - Dependency Graph and Query Scope
* ADR-0044 - Adopt The Web UI Operational Interaction Stack

---

# Review

Revisit this decision if a future phase needs OpenPDM to raise ADR-0030's traversal bound (larger or unbounded graphs) in a way React Flow's performance profile does not comfortably cover, if React Flow's maintenance stalls, or if the project decides pan/zoom/drag interaction is not worth its dependency and bundle-size cost after real usage -- any of those would justify replacing it with a narrower, hand-rolled diagram instead.
