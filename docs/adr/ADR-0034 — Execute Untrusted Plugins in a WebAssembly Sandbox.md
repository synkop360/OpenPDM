# ADR-0034 — Execute Untrusted Plugins in a WebAssembly Sandbox

**Status:** Proposed

---

# Context

Phase 4 introduces executable Official Plugins and Community Plugins. A plugin package is external input and may be malformed, compromised or intentionally hostile. Requiring an administrator to trust arbitrary native code is insufficient for an Engineering Collaboration Platform that stores sensitive engineering data.

Plugins must use the Extension API, must not import Platform Module internals and must not gain ambient access to the host operating system. A plugin failure, infinite loop or memory-exhaustion attempt must not terminate or corrupt the Platform Core.

OpenPDM therefore requires an execution boundary designed for untrusted code, explicit capabilities and defense in depth.

---

# Decision

OpenPDM will execute plugin logic as **WebAssembly Components** in a **Wasmtime sandbox** hosted by a managed local runtime worker.

Plugin packages contain an `openpdm-plugin.json` manifest and a WebAssembly Component. Phase 4 does not load native libraries, Python wheels, scripts or arbitrary host executables from plugin packages.

The Extension API v1 component contract is expressed with WebAssembly Interface Types. A plugin may interact with OpenPDM only through imports explicitly linked by the runtime. The worker does not provide WASI filesystem, network, environment, process, clock or random capabilities unless a future ADR defines and authorizes a specific capability. Platform Module interfaces, database connections, object-storage credentials and host secrets are never linked into a plugin.

The runtime applies all of the following controls to every invocation:

* bounded linear memory and table growth;
* deterministic fuel limits and a wall-clock deadline;
* bounded request and response sizes;
* no inherited standard input;
* captured, size-limited and control-character-sanitized diagnostic output;
* a fresh Store for each invocation so mutable guest state is not shared implicitly;
* termination and failure recording when any limit is exceeded.

The Wasmtime worker runs in a separate operating-system process with only the files required to load content-addressed plugin components. It communicates with the Platform Core through a private, authenticated, versioned protocol. Compromising the worker must not directly expose Platform Core memory.

## Package integrity

Every installed package is copied into OpenPDM-managed immutable storage and addressed by a SHA-256 digest recorded in the plugin registry. The digest is verified before every activation. Installation rejects archives with path traversal, links, duplicate entries, unexpected files or size-limit violations.

Phase 4 supports administrator-approved local installation. Publisher signature verification is required before remote registry installation or unattended upgrades may be introduced. Integrity verification detects replacement after approval; it does not claim publisher identity.

## Security boundary

Plugin output is treated as untrusted data. The Platform Core validates schemas, reauthorizes every requested operation and escapes or sanitizes output before logging or presentation. The sandbox reduces the effect of hostile guest code but does not replace dependency patching, operating-system isolation or security testing.

Official Plugins and Community Plugins use the same package format, sandbox, resource limits and Extension API.

---

# Consequences

## Positive

* Plugin packages cannot inject native host code through the supported runtime.
* Deny-by-default imports prevent ambient filesystem, network and process access.
* Memory, computation, time and message limits contain common denial-of-service attempts.
* A separate worker adds process isolation around the WebAssembly sandbox.
* Language-neutral component contracts allow future plugin SDKs without changing the Extension API boundary.

## Trade-offs

* Plugin authors must compile supported languages to WebAssembly Components.
* Wasmtime and the Component Model add a new runtime and toolchain to deployment and development.
* Some engineering integrations that require local applications or devices will need separately designed broker capabilities.
* No sandbox can guarantee the absence of implementation vulnerabilities; Wasmtime updates become security-sensitive dependencies.

These trade-offs are acceptable because OpenPDM prioritizes protection of engineering data and enforceable extension boundaries over native plugin convenience.

---

# Alternatives Considered

## Native code in a managed subprocess

Rejected because native plugin code retains the operating-system permissions of the worker and can access files, the network and other host resources outside the Extension API.

## In-process plugin imports

Rejected because hostile or defective code could access Platform Core internals and corrupt shared process state.

## Containers

Not selected as the Phase 4 contract because container availability and isolation vary across self-hosted platforms. Deployment may still place the runtime worker in an additional container as defense in depth.

## Remote plugin workers

Deferred because they introduce distributed authentication, deployment and availability requirements. The private worker protocol may support that evolution only through a future ADR.

---

# References

* Wasmtime security model — https://docs.wasmtime.dev/security.html
* Wasmtime execution interruption — https://docs.wasmtime.dev/examples-interrupting-wasm.html
* WebAssembly Component Model design — https://component-model.bytecodealliance.org/design/why-component-model.html

---

# Review

Reconsider this decision if Wasmtime cannot satisfy an objective OpenPDM security requirement, a required engineering integration cannot be expressed through safe brokered capabilities, or a stronger portable sandbox becomes demonstrably more suitable.
