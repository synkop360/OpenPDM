# projectctl

`projectctl` is an internal maintenance tool for the OpenPDM repository.

Its purpose is to synchronize the GitHub Project with a declarative configuration stored in `project.yaml`.

It is **not** part of OpenPDM.

It is **not** intended to become an independent project.

It exists solely to reduce manual project management.

---

# Philosophy

The Git repository is the source of truth.

GitHub is a projection of that truth.

All project management data must be stored inside `project.yaml`.

No manual modifications should be performed on GitHub whenever they can be expressed declaratively.

---

# Responsibilities

projectctl is responsible for synchronizing:

* Labels
* Milestones
* GitHub Project custom fields
* Issues
* Issue labels
* Issue milestones
* Issue custom fields

It is **not** responsible for:

* Software architecture
* Source code generation
* Documentation generation
* Release management

---

# Design Principles

Keep projectctl simple.

Prefer procedural code over abstractions.

Prefer explicit code over generic frameworks.

Avoid unnecessary dependencies.

Readability is more important than extensibility.

The tool should remain understandable by a new contributor in less than one hour.

---

# Repository Structure

```text
.github/automation/project/

README.md
AGENTS.md
project.yaml

apply.py
validate.py
export.py

requirements.txt
```

---

# Scripts

## validate.py

Validates the project configuration.

Checks include:

* YAML syntax
* duplicate identifiers
* invalid references
* unknown field values
* missing required fields

This script never modifies GitHub.

## apply.py

Synchronizes GitHub with `project.yaml`.

The script is idempotent.

Running it multiple times should converge to the same GitHub Project without creating duplicate configured resources.

## export.py

Reserved for future use.

Its objective will be exporting an existing GitHub Project back into `project.yaml`.

---

# Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Validate the configuration:

```bash
python validate.py
```

Apply the configuration:

```bash
GITHUB_TOKEN=... python apply.py
```

Always validate before applying. `apply.py` also validates before contacting GitHub.

---

# Configuration Shape

`project.yaml` contains:

* `project`: GitHub Project metadata used by projectctl.
* `repository`: GitHub repository owner and name.
* `labels`: repository labels to create or update.
* `milestones`: repository milestones to create or update.
* `fields`: GitHub Project custom fields to create or update.
* `issues`: repository issues to create or update.
* `roadmap`: roadmap phases; phase `epics` are treated as issues.

Supported custom field types are:

* `text`
* `number`
* `date`
* `single_select`

---

# Scope

If projectctl becomes difficult to understand or maintain, simplify it.

Do not transform it into a reusable framework.

Its only purpose is supporting the OpenPDM repository.
