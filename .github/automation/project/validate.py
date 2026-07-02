"""Validate projectctl configuration.

The Git repository is the source of truth. This script checks that
project.yaml is internally consistent before apply.py contacts GitHub.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).with_name("project.yaml")
SUPPORTED_FIELD_TYPES = {"text", "number", "date", "single_select"}


class ValidationFailure(Exception):
    """Raised when project.yaml cannot be used safely."""


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            loaded_config = yaml.safe_load(config_file)
    except yaml.YAMLError as exc:
        raise ValidationFailure(f"invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ValidationFailure(f"cannot read {path}: {exc}") from exc

    if loaded_config is None:
        raise ValidationFailure(f"{path} is empty")
    if not isinstance(loaded_config, dict):
        raise ValidationFailure("project.yaml must contain a mapping at the top level")
    return loaded_config


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    project = require_mapping(config, "project", errors)
    repository = require_mapping(config, "repository", errors)
    labels = require_list(config, "labels", errors)
    fields = require_list(config, "fields", errors)
    milestones = require_list(config, "milestones", errors)
    issues = optional_list(config, "issues", errors)
    roadmap = optional_list(config, "roadmap", errors)

    if project is not None:
        require_string(project, "project", "name", errors)
        optional_string(project, "project", "description", errors)

    if repository is not None:
        require_string(repository, "repository", "owner", errors)
        require_string(repository, "repository", "name", errors)

    label_names = validate_labels(labels, errors)
    field_options = validate_fields(fields, errors)
    milestone_titles = validate_milestones(milestones, errors)
    all_issues = validate_roadmap(roadmap, milestone_titles, errors)
    all_issues.extend(validate_issues(issues, "issues", errors))

    validate_unique_issue_titles(all_issues, errors)
    validate_issue_references(all_issues, label_names, milestone_titles, field_options, errors)
    return errors


def require_mapping(parent: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any] | None:
    if key not in parent:
        errors.append(f"missing required section: {key}")
        return None
    value = parent[key]
    if not isinstance(value, dict):
        errors.append(f"{key} must be a mapping")
        return None
    return value


def require_list(parent: dict[str, Any], key: str, errors: list[str]) -> list[Any]:
    if key not in parent:
        errors.append(f"missing required section: {key}")
        return []
    value = parent[key]
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    return value


def require_child_list(
    parent: dict[str, Any], parent_name: str, key: str, errors: list[str]
) -> list[Any]:
    if key not in parent:
        errors.append(f"{parent_name}.{key} is required and must be a list")
        return []
    value = parent[key]
    if not isinstance(value, list):
        errors.append(f"{parent_name}.{key} must be a list")
        return []
    return value


def optional_list(parent: dict[str, Any], key: str, errors: list[str]) -> list[Any]:
    if key not in parent or parent[key] is None:
        return []
    value = parent[key]
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    return value


def require_string(parent: dict[str, Any], parent_name: str, key: str, errors: list[str]) -> str | None:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{parent_name}.{key} is required and must be a non-empty string")
        return None
    return value


def optional_string(parent: dict[str, Any], parent_name: str, key: str, errors: list[str]) -> str | None:
    value = parent.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{parent_name}.{key} must be a string")
        return None
    return value


def optional_bool(parent: dict[str, Any], parent_name: str, key: str, errors: list[str]) -> bool | None:
    value = parent.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        errors.append(f"{parent_name}.{key} must be true or false")
        return None
    return value


def validate_labels(labels: list[Any], errors: list[str]) -> set[str]:
    names: set[str] = set()
    for index, label in enumerate(labels):
        item_name = f"labels[{index}]"
        if not isinstance(label, dict):
            errors.append(f"{item_name} must be a mapping")
            continue
        name = require_string(label, item_name, "name", errors)
        optional_string(label, item_name, "description", errors)
        color = require_string(label, item_name, "color", errors)
        if name is not None:
            add_unique(names, name, item_name, "label name", errors)
        if color is not None and not is_hex_color(color):
            errors.append(f"{item_name}.color must be a 6-character hex color without '#': {color}")
    return names


def validate_fields(fields: list[Any], errors: list[str]) -> dict[str, set[str] | None]:
    field_options: dict[str, set[str] | None] = {}
    field_names: set[str] = set()

    for index, field in enumerate(fields):
        item_name = f"fields[{index}]"
        if not isinstance(field, dict):
            errors.append(f"{item_name} must be a mapping")
            continue

        name = require_string(field, item_name, "name", errors)
        field_type = require_string(field, item_name, "type", errors)
        if name is not None:
            add_unique(field_names, name, item_name, "field name", errors)

        if field_type is not None and field_type not in SUPPORTED_FIELD_TYPES:
            errors.append(
                f"{item_name}.type must be one of {sorted(SUPPORTED_FIELD_TYPES)}: {field_type}"
            )

        if field_type == "single_select":
            options = require_child_list(field, item_name, "options", errors)
            option_names = validate_field_options(options, item_name, errors)
            if name is not None:
                field_options[name] = option_names
        else:
            if "options" in field:
                errors.append(f"{item_name}.options is only supported for single_select fields")
            if name is not None:
                field_options[name] = None

    return field_options


def validate_field_options(options: list[Any], field_path: str, errors: list[str]) -> set[str]:
    option_names: set[str] = set()
    for index, option in enumerate(options):
        option_path = f"{field_path}.options[{index}]"
        if isinstance(option, str):
            if option.strip():
                add_unique(option_names, option, option_path, "field option", errors)
            else:
                errors.append(f"{option_path} must not be empty")
            continue
        if isinstance(option, dict):
            name = require_string(option, option_path, "name", errors)
            optional_string(option, option_path, "color", errors)
            optional_string(option, option_path, "description", errors)
            if name is not None:
                add_unique(option_names, name, option_path, "field option", errors)
            continue
        errors.append(f"{option_path} must be a string or mapping")
    return option_names


def validate_milestones(milestones: list[Any], errors: list[str]) -> set[str]:
    titles: set[str] = set()
    for index, milestone in enumerate(milestones):
        item_name = f"milestones[{index}]"
        if not isinstance(milestone, dict):
            errors.append(f"{item_name} must be a mapping")
            continue
        title = require_string(milestone, item_name, "title", errors)
        optional_string(milestone, item_name, "description", errors)
        optional_string(milestone, item_name, "due_on", errors)
        optional_string(milestone, item_name, "state", errors)
        if title is not None:
            add_unique(titles, title, item_name, "milestone title", errors)
        state = milestone.get("state")
        if state is not None and state not in {"open", "closed"}:
            errors.append(f"{item_name}.state must be 'open' or 'closed'")
    return titles


def validate_roadmap(
    roadmap: list[Any], milestone_titles: set[str], errors: list[str]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    phase_names: set[str] = set()

    for index, phase in enumerate(roadmap):
        phase_path = f"roadmap[{index}]"
        if not isinstance(phase, dict):
            errors.append(f"{phase_path} must be a mapping")
            continue
        phase_name = require_string(phase, phase_path, "phase", errors)
        milestone = require_string(phase, phase_path, "milestone", errors)
        optional_string(phase, phase_path, "description", errors)
        epics = optional_list(phase, "epics", errors)

        if phase_name is not None:
            add_unique(phase_names, phase_name, phase_path, "roadmap phase", errors)
        if milestone is not None and milestone not in milestone_titles:
            errors.append(f"{phase_path}.milestone references unknown milestone: {milestone}")

        phase_issues = validate_issues(epics, f"{phase_path}.epics", errors)
        for issue in phase_issues:
            issue.setdefault("milestone", milestone)
        issues.extend(phase_issues)

    return issues


def validate_issues(issues: list[Any], parent_name: str, errors: list[str]) -> list[dict[str, Any]]:
    validated_issues: list[dict[str, Any]] = []
    titles: set[str] = set()

    for index, issue in enumerate(issues):
        item_name = f"{parent_name}[{index}]"
        if not isinstance(issue, dict):
            errors.append(f"{item_name} must be a mapping")
            continue
        title = require_string(issue, item_name, "title", errors)
        optional_string(issue, item_name, "body", errors)
        optional_string(issue, item_name, "milestone", errors)
        optional_bool(issue, item_name, "closed", errors)
        labels = optional_list(issue, "labels", errors)
        fields = issue.get("fields", {})
        if not isinstance(fields, dict):
            errors.append(f"{item_name}.fields must be a mapping")
            fields = {}
        if title is not None:
            add_unique(titles, title, item_name, "issue title", errors)
        for label_index, label in enumerate(labels):
            if not isinstance(label, str) or not label.strip():
                errors.append(f"{item_name}.labels[{label_index}] must be a non-empty string")
        validated_issues.append(issue)

    return validated_issues


def validate_unique_issue_titles(issues: list[dict[str, Any]], errors: list[str]) -> None:
    titles: set[str] = set()
    for issue in issues:
        title = issue.get("title")
        if not isinstance(title, str):
            continue
        add_unique(titles, title, f"issue '{title}'", "issue title", errors)


def validate_issue_references(
    issues: list[dict[str, Any]],
    label_names: set[str],
    milestone_titles: set[str],
    field_options: dict[str, set[str] | None],
    errors: list[str],
) -> None:
    for issue in issues:
        issue_title = issue.get("title", "<unknown issue>")
        for label in issue.get("labels", []) or []:
            if label not in label_names:
                errors.append(f"issue '{issue_title}' references unknown label: {label}")
        milestone = issue.get("milestone")
        if milestone is not None and milestone not in milestone_titles:
            errors.append(f"issue '{issue_title}' references unknown milestone: {milestone}")

        fields = issue.get("fields", {}) or {}
        if not isinstance(fields, dict):
            continue
        for field_name, value in fields.items():
            if field_name not in field_options:
                errors.append(f"issue '{issue_title}' references unknown field: {field_name}")
                continue
            allowed_options = field_options[field_name]
            if allowed_options is not None and value not in allowed_options:
                errors.append(
                    f"issue '{issue_title}' uses unknown value for field '{field_name}': {value}"
                )


def add_unique(
    seen_values: set[str], value: str, item_name: str, label: str, errors: list[str]
) -> None:
    if value in seen_values:
        errors.append(f"duplicate {label}: {value} at {item_name}")
        return
    seen_values.add(value)


def is_hex_color(value: str) -> bool:
    return len(value) == 6 and all(character in "0123456789abcdefABCDEF" for character in value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate projectctl configuration.")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(CONFIG_PATH),
        help="Path to project.yaml. Defaults to the file next to validate.py.",
    )
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config))
        errors = validate_config(config)
    except ValidationFailure as exc:
        print(f"projectctl validation failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("projectctl validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("projectctl validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
