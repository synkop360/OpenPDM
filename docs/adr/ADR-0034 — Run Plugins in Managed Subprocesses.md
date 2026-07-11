# ADR-0034 — Run Plugins in Managed Subprocesses

**Status:** Proposed

---

# Context

Phase 4 introduces executable Official Plugins and Community Plugins. Plugins must use the Extension API, must not import Platform Module internals and must not be able to terminate or corrupt the Platform Core process through an ordinary failure.

OpenPDM remains a modular monolith, but plugin execution is an extension boundary rather than a Platform Module boundary. The first runtime must remain understandable for self-hosted deployments while providing meaningful failure containment.

---

# Decision

OpenPDM will execute each enabled plugin in a **managed local subprocess**.

Plugins are distributed as Python wheel packages containing an `openpdm-plugin.json` manifest and an executable entry point. Installation is an explicit platform-administration operation; OpenPDM does not download packages from arbitrary registries automatically.

The Platform Core communicates with plugin subprocesses through a versioned JSON message protocol owned by the Extension API. Plugins receive capability-scoped requests and data, never database sessions, repositories, credentials or Public Module Interfaces.

The runtime supervisor owns process start, readiness, timeout, restart and shutdown. A crashed or unresponsive plugin is marked failed and disabled after a bounded restart attempt. Its failure must not terminate the Platform Core or another plugin.

Plugin subprocesses are a failure-containment boundary, not a complete hostile-code sandbox. Administrators must install only trusted packages. Strong operating-system sandboxing and remote plugin workers are deferred.

---

# Consequences

## Positive

* Plugin failures are isolated from the Platform Core process.
* Plugins cannot import in-memory Platform Module implementations.
* The Extension API message protocol is testable independently of plugin code.
* Official Plugins and Community Plugins use the same runtime.

## Trade-offs

* Subprocess lifecycle and communication add operational complexity.
* Serialization prevents passing rich in-process objects.
* Installed plugin code still has the operating-system permissions of its process unless deployment hardening restricts them.

These trade-offs are acceptable because Phase 4 needs enforceable process and contract boundaries without introducing distributed services.

---

# Alternatives Considered

## In-process imports

Rejected because an extension could import internals, block the application or corrupt shared process state.

## Containers or remote workers

Deferred because they would introduce orchestration and distributed-operation requirements beyond the modular monolith deployment model.

---

# Review

Reconsider this decision if production deployments require hostile-code isolation, independent plugin scaling or non-Python plugin runtimes.
