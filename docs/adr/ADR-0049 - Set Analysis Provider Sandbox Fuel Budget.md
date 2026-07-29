# ADR-0049 - Set Analysis Provider Sandbox Fuel Budget

**Status:** Accepted

---

# Context

ADR-0034 requires bounded computation for every untrusted plugin invocation.
ADR-0047 authorizes a bounded analysis provider to receive up to 5 MiB of
Representation content. The existing generic plugin-invocation fuel default of
25,000,000 is insufficient for an analysis provider to decode the 174 KiB
`AssemblyExample.FCStd` fixture, even before it performs file-format-specific
work. The current 100,000,000 maximum also prevents a configured analysis
provider invocation from reaching the measured minimum successful budget of
150,000,000.

The Platform Core must preserve the sandbox limits in ADR-0034 while allowing
the accepted generic analysis input contract to be usable. This is an
execution-resource decision, not a FreeCAD or mechanical-engineering decision.

---

# Decision

OpenPDM will use a distinct, generic analysis-provider fuel setting. Its
default is **200,000,000** fuel units and its validated maximum is
**500,000,000** fuel units. The setting applies only to invocations through the
`analysis_provider` capability; other provider and event-hook invocations keep
the existing plugin-runtime fuel setting and its current default.

The analysis-provider setting is passed to the existing Wasmtime sandbox worker
for each invocation. It does not relax the existing wall-clock deadline,
linear-memory limit, request/response limits, fresh-store isolation, denied
ambient capabilities, authorization checks, or Extension API boundary.

The 200,000,000 default provides headroom over the measured 150,000,000 minimum
for decoding the representative native fixture. It does not authorize larger
inputs than ADR-0047 or change the interpretation of plugin content.

---

# Consequences

## Positive

* The 5 MiB analysis input contract in ADR-0047 can be exercised without
  weakening its content bound.
* Analysis workloads receive an explicit, independently configurable resource
  budget while ordinary plugin invocations retain their existing default.
* The Platform Core remains domain-agnostic: it governs sandbox resources, not
  file formats or engineering semantics.

## Trade-offs

* Analysis-provider invocations may consume more bounded CPU time before fuel
  termination.
* Operators must review installed providers before increasing the setting above
  its default.
* Providers with workloads beyond this budget need a separate decision rather
  than an unbounded configuration change.

These trade-offs are acceptable because the existing sandbox controls remain
enforced and the budget is necessary to honor the accepted bounded-input
contract.

---

# Alternatives Considered

## Increase the fuel budget for every plugin invocation

Rejected because analysis-provider content processing has a distinct workload.
Raising the default for all providers and hooks would expand their resource
budget without a demonstrated need.

## Reduce the ADR-0047 content limit

Rejected because the 5 MiB contract is already accepted and a 174 KiB native
fixture demonstrates that the incompatibility is the sandbox budget, not an
excessive input size.

## Permit unbounded fuel for analysis providers

Rejected because it would violate ADR-0034's bounded-computation requirement.

---

# References

* ADR-0034 - Execute Untrusted Plugins in a WebAssembly Sandbox
* ADR-0047 - Authorize Bounded Representation Analysis Inputs

---

# Review

Reconsider this decision if a representative provider cannot complete a
permitted 5 MiB analysis within the default budget and existing wall-clock and
memory controls, or if measured resource use shows that the maximum is not an
acceptable operational bound.
