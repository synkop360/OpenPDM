# ADR-0031 — Generic References Scope

**Status:** Accepted

---

# Context

The Phase 3 roadmap lists `generic references` alongside Asset relationships, dependency graph and graph queries.

OpenPDM needs an explicit distinction between:

* a semantic link between two Assets managed by OpenPDM;
* a lightweight pointer to something outside OpenPDM or not yet resolved into an Asset.

Without this distinction, the Asset Graph could become polluted by fake Assets, unresolved file dependencies or arbitrary external URLs treated as first-class graph nodes.

---

# Decision

OpenPDM distinguishes **Relationship** and **Reference** in Phase 3.

## Definitions

* `Relationship` = semantic link between two Assets.
* `Reference` = lightweight pointer to an external or unresolved object.

Phase 3 `Reference` records contain the following fields:

* `id`
* `source_asset_id`
* `reference_type`
* `target_uri`
* `label`
* `metadata`
* `created_by`
* `created_at`

## Reference rules

Phase 3 references follow these rules:

* references may point outside OpenPDM;
* references are not graph edges between two Assets;
* references may later be resolved into Relationships;
* the Platform Core stores references generically and does not interpret plugin-specific semantics.

## Examples

Examples of Phase 3 references include:

* external URL;
* supplier datasheet link;
* unresolved CAD dependency;
* external document identifier;
* legacy file path.

## Explicit exclusions

Phase 3 does **not**:

* treat every external URL as an Asset;
* create fake Assets for unresolved dependencies;
* introduce plugin-specific reference semantics into the Platform Core.

---

# Consequences

## Positive

* The Asset Graph stays focused on real Asset-to-Asset links.
* External and unresolved pointers can be stored without polluting the Asset model.
* Future resolution workflows can convert references into relationships intentionally.

## Trade-offs

* Phase 3 introduces one more generic concept alongside relationships.
* Clients must distinguish graph edges from references explicitly.
* Some future plugin workflows may require additional reference-handling decisions.

These trade-offs are acceptable because OpenPDM currently needs a clean generic distinction between Asset links and unresolved or external pointers.

---

# Alternatives Considered

## Model All References as Relationships

Rejected because it would blur the distinction between Assets managed by OpenPDM and unresolved or external targets.

## Create Placeholder Assets for Unresolved Targets

Rejected because it would pollute the Asset Graph with artificial Platform Core entities that do not yet represent real OpenPDM Assets.

## Defer References Entirely

Rejected because the roadmap explicitly includes generic references in Phase 3 and unresolved or external pointers are a useful generic capability.

---

# Review

This decision should be revisited when plugin-driven resolution workflows, richer external-link management or Digital Thread needs require additional reference semantics.
