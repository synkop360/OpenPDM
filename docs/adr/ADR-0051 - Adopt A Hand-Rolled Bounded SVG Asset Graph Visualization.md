# ADR-0051 - Adopt A Hand-Rolled Bounded SVG Asset Graph Visualization

**Status:** Proposed

---

# Context

The Relationships & Graph tab's "Bounded graph summary" card currently shows the result of the existing `getAssetGraph` call as six text tiles (node count, relationship count, direction, max depth, path target, path exists). A reader has to reconstruct the actual shape of the graph from those numbers; there is no visualization of the graph itself, even though the response already carries everything needed to draw one (`nodes: GraphNode[]`, `relationships: Relationship[]`).

ADR-0030 bounds what this graph can ever contain: a default traversal depth of 3, a hard maximum of 10, and an explicit exclusion of graph analytics, shortest-path optimization and centrality calculations. Whatever renders this data must stay inside that bound and must not introduce a new backend call to get there -- the `getAssetGraph` response the Relationships & Graph tab already fetches is the only input.

ADR-0044 adopted React Router, Radix primitives, Lucide icons, repository-owned CSS tokens, Vitest and Playwright as the Web UI's interaction stack, and asked contributors to prefer existing primitives over ad hoc components. None of those primitives cover diagram rendering, so this decision has to weigh two real options rather than default to either extreme:

* build a small, purpose-built SVG diagram directly against the bounded `AssetGraph` shape, with no new dependency; or
* adopt a graph-rendering library (for example `reactflow` or `vis-network`) that provides automatic layout, pan/zoom and drag interaction out of the box.

Limiting dependencies does not mean avoiding them at all cost -- a library is the right call when it saves real complexity the project would otherwise have to build and maintain itself. The question is whether that complexity exists here, given how small and bounded this graph is by construction.

---

# Decision

OpenPDM will render the Asset Graph as a hand-rolled, dependency-free SVG diagram instead of adopting a graph-rendering library.

A new presentational component reads the same `AssetGraph` response the Relationships & Graph tab already fetches (`nodes`, `relationships`, `direction`, `max_depth`, `target_asset_id`, `path_exists`, `has_cycle`) and replaces the six-tile summary card with it. No new API call is introduced; the component does not request depth, direction or traversal behavior beyond what ADR-0030 already bounds and the tab already queries.

The diagram uses a deterministic layout, not a physics-based or force-directed one: the selected Asset is drawn at the center, and the fetched nodes are placed around it grouped by their relationship to the center, with SVG lines connecting related nodes and arrowheads showing relationship direction. Because the node count is bounded by ADR-0030's depth limits, a deterministic layout is sufficient -- there is no need for collision-avoidance or iterative layout algorithms a library would justify for large, unbounded graphs.

Each node remains a real DOM element (an SVG `<g>` with an accessible name built from the Asset's name and status), and clicking a node calls the tab's existing `onSelectAsset` handler exactly like the current "Open asset" buttons do -- no new navigation or authorization path is introduced. A visually-hidden text equivalent of the diagram's content ships alongside the SVG so the graph remains usable without vision, consistent with the accessibility bar the rest of the Web UI holds (verified by the existing axe-core coverage in `operational-web-ui.spec.ts`).

`has_cycle` and `path_exists` continue to render as their own status indicators near the diagram rather than being encoded only visually, so that information stays available to assistive technology and to a quick glance alike.

---

# Consequences

## Positive

* No new dependency is added to `frontend/package.json`; the Web UI's audited dependency surface and bundle size stay unchanged.
* The diagram is plain SVG in the DOM, so it is directly assertable with Playwright and Testing Library the same way the rest of the Web UI already is, with no canvas-pixel or library-internals testing needed.
* Accessibility stays under OpenPDM's own control: node labels, roles and the text-equivalent fallback follow the same conventions as the rest of the Web UI instead of depending on a third-party library's accessibility support.
* The bounded, deterministic layout is straightforward to reason about and keeps the component small, matching the scope ADR-0030 already set for this data.

## Trade-offs

* The diagram will not get automatic collision avoidance, pan/zoom or drag-to-rearrange; if a future phase needs those, this decision will need revisiting rather than just configuring a library that already had them.
* A hand-rolled layout has to be maintained by OpenPDM contributors instead of a library's maintainers; layout bugs at the edges of the depth bound (many nodes at one level) are OpenPDM's to find and fix.
* This decision does not scale to graph analytics or large unbounded graphs -- it deliberately only has to work within ADR-0030's existing bound, and would need to be revisited (not extended) if that bound changes.

---

# Alternatives Considered

## Adopt `reactflow`

Rejected for this phase. `reactflow` provides real value -- automatic layout, pan/zoom, drag -- but that value is aimed at graphs larger and more open-ended than what ADR-0030 permits here; the Asset Graph this component renders is capped at a handful of hops by design, not sized to need automatic layout. Its DOM structure and canvas-backed edges are also harder to assert against with the project's existing Testing Library and Playwright conventions than a plain SVG tree is, and its accessibility behavior for keyboard and screen-reader users is not to the bar the rest of the Web UI already holds via Radix primitives.

## Adopt `vis-network`

Rejected because it renders to `<canvas>`, which is opaque to Playwright's DOM-based assertions and to screen readers, and it is a general-purpose network visualization library sized for graphs well beyond ADR-0030's bounded traversal scope. Adopting it would mean carrying a dependency whose main strengths -- large-graph performance and physics-based layout -- this project's bounded graph will never exercise.

## Extend the existing six-tile summary instead of visualizing

Rejected because it does not address the actual problem: a reader still cannot see the graph's shape, only counts describing it. The issue this ADR resolves specifically asks for a visualization built from data the tab already has, not a richer summary of the same non-visual kind.

---

# References

* ADR-0030 - Dependency Graph and Query Scope
* ADR-0044 - Adopt The Web UI Operational Interaction Stack

---

# Review

Revisit this decision if a future phase needs OpenPDM to raise ADR-0030's traversal bound (larger or unbounded graphs), needs pan/zoom/drag interaction, or needs to render more than one Asset Graph on screen at once -- any of those would justify the layout and interaction work a graph-rendering library already provides.
