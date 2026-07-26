"""Synchronize GitHub from projectctl configuration."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from validate import CONFIG_PATH, ValidationFailure, load_config, validate_config


REST_API_URL = "https://api.github.com"
GRAPHQL_API_URL = "https://api.github.com/graphql"


class ApplyFailure(Exception):
    """Raised when GitHub synchronization cannot continue safely."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply projectctl configuration to GitHub.")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(CONFIG_PATH),
        help="Path to project.yaml. Defaults to the file next to apply.py.",
    )
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config))
        validation_errors = validate_config(config)
        if validation_errors:
            print("projectctl validation failed:", file=sys.stderr)
            for error in validation_errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ApplyFailure("GITHUB_TOKEN is required")

        session = create_session(token)
        apply_config(session, config)
    except ValidationFailure as exc:
        print(f"projectctl validation failed: {exc}", file=sys.stderr)
        return 1
    except ApplyFailure as exc:
        print(f"projectctl apply failed: {exc}", file=sys.stderr)
        return 1

    print("projectctl apply completed.")
    return 0


def create_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def apply_config(session: requests.Session, config: dict[str, Any]) -> None:
    owner = config["repository"]["owner"]
    repo = config["repository"]["name"]
    project_name = config["project"]["name"]

    print(f"Synchronizing repository {owner}/{repo}.")
    sync_labels(session, owner, repo, config.get("labels", []))
    milestone_map = sync_milestones(session, owner, repo, config.get("milestones", []))

    print(f"Synchronizing GitHub Project '{project_name}'.")
    project = find_project(session, owner, repo, project_name)
    project_fields = sync_project_fields(session, project["id"], config.get("fields", []))

    issues = collect_issues(config)
    issue_nodes = sync_issues(session, owner, repo, issues, milestone_map)
    sync_sub_issues(session, owner, repo, issues, issue_nodes)
    sync_project_items(session, project["id"], project_fields, issues, issue_nodes)


def rest_request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    expected_statuses: set[int],
    **kwargs: Any,
) -> Any:
    response = session.request(method, f"{REST_API_URL}{path}", **kwargs)
    if response.status_code not in expected_statuses:
        raise ApplyFailure(
            f"GitHub REST {method} {path} failed with {response.status_code}: {response.text}"
        )
    if response.status_code == 204 or not response.text:
        return None
    return response.json()


def graphql_request(
    session: requests.Session, query: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = session.post(GRAPHQL_API_URL, json={"query": query, "variables": variables or {}})
    if response.status_code != 200:
        raise ApplyFailure(f"GitHub GraphQL request failed with {response.status_code}: {response.text}")
    payload = response.json()
    if payload.get("errors"):
        raise ApplyFailure(f"GitHub GraphQL request failed: {payload['errors']}")
    return payload["data"]


def get_all_pages(
    session: requests.Session, path: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    page = 1
    values: list[dict[str, Any]] = []
    while True:
        page_params = dict(params or {})
        page_params.update({"per_page": 100, "page": page})
        data = rest_request(
            session,
            "GET",
            path,
            expected_statuses={200},
            params=page_params,
        )
        values.extend(data)
        if len(data) < 100:
            return values
        page += 1


def sync_labels(
    session: requests.Session, owner: str, repo: str, labels: list[dict[str, Any]]
) -> None:
    existing_labels = {
        label["name"]: label
        for label in get_all_pages(session, f"/repos/{owner}/{repo}/labels")
    }

    for label in labels:
        name = label["name"]
        payload = {
            "name": name,
            "color": label["color"],
            "description": label.get("description", ""),
        }
        existing = existing_labels.get(name)
        if existing is None:
            print(f"Creating label: {name}")
            rest_request(
                session,
                "POST",
                f"/repos/{owner}/{repo}/labels",
                expected_statuses={201},
                json=payload,
            )
            continue

        if existing.get("color", "").lower() != payload["color"].lower() or (
            existing.get("description") or ""
        ) != payload["description"]:
            print(f"Updating label: {name}")
            rest_request(
                session,
                "PATCH",
                f"/repos/{owner}/{repo}/labels/{quote(name, safe='')}",
                expected_statuses={200},
                json=payload,
            )


def sync_milestones(
    session: requests.Session, owner: str, repo: str, milestones: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    existing_milestones = {
        milestone["title"]: milestone
        for milestone in get_all_pages(
            session, f"/repos/{owner}/{repo}/milestones", {"state": "all"}
        )
    }
    milestone_map: dict[str, dict[str, Any]] = {}

    for milestone in milestones:
        title = milestone["title"]
        payload = milestone_payload(milestone)
        existing = existing_milestones.get(title)
        if existing is None:
            print(f"Creating milestone: {title}")
            created = rest_request(
                session,
                "POST",
                f"/repos/{owner}/{repo}/milestones",
                expected_statuses={201},
                json=payload,
            )
            milestone_map[title] = created
            continue

        if milestone_needs_update(existing, payload):
            print(f"Updating milestone: {title}")
            existing = rest_request(
                session,
                "PATCH",
                f"/repos/{owner}/{repo}/milestones/{existing['number']}",
                expected_statuses={200},
                json=payload,
            )
        milestone_map[title] = existing

    return milestone_map


def milestone_payload(milestone: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "title": milestone["title"],
        "description": milestone.get("description", ""),
        "state": milestone.get("state", "open"),
    }
    if milestone.get("due_on"):
        payload["due_on"] = milestone["due_on"]
    return payload


def milestone_needs_update(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    if existing.get("description") != desired.get("description"):
        return True
    if existing.get("state") != desired.get("state"):
        return True
    if desired.get("due_on") and existing.get("due_on") != desired.get("due_on"):
        return True
    return False


def find_project(
    session: requests.Session, owner: str, repo: str, project_name: str
) -> dict[str, Any]:
    query = """
    query($owner: String!, $repo: String!, $query: String!) {
      repository(owner: $owner, name: $repo) {
        owner {
          __typename
          ... on Organization {
            projectsV2(first: 100, query: $query) {
              nodes { id title number }
            }
          }
          ... on User {
            projectsV2(first: 100, query: $query) {
              nodes { id title number }
            }
          }
        }
      }
    }
    """
    data = graphql_request(session, query, {"owner": owner, "repo": repo, "query": project_name})
    repository = data.get("repository")
    if repository is None:
        raise ApplyFailure(f"repository not found: {owner}/{repo}")
    project_owner = repository["owner"]
    projects = project_owner.get("projectsV2", {}).get("nodes", [])
    for project in projects:
        if project["title"] == project_name:
            return project
    raise ApplyFailure(f"GitHub Project not found for owner '{owner}': {project_name}")


def sync_project_fields(
    session: requests.Session, project_id: str, desired_fields: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    existing_fields = get_project_fields(session, project_id)
    fields_by_name = project_fields_by_name(existing_fields)

    for field in desired_fields:
        name = field["name"]
        existing = fields_by_name.get(name)
        if existing is None:
            print(f"Creating project field: {name}")
            existing = create_project_field(session, project_id, field)
        else:
            ensure_field_type(name, existing, field)
            if field["type"] == "single_select":
                sync_single_select_options(session, existing, field)
        fields_by_name[name] = existing

    return get_project_fields_by_name(session, project_id)


def get_project_fields_by_name(session: requests.Session, project_id: str) -> dict[str, dict[str, Any]]:
    return project_fields_by_name(get_project_fields(session, project_id))


def project_fields_by_name(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fields_by_name: dict[str, dict[str, Any]] = {}
    for field in fields:
        name = field.get("name")
        if name:
            fields_by_name[name] = field
    return fields_by_name


def get_project_fields(session: requests.Session, project_id: str) -> list[dict[str, Any]]:
    query = """
    query($projectId: ID!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              __typename
              ... on ProjectV2Field {
                id
                name
                dataType
              }
              ... on ProjectV2SingleSelectField {
                id
                name
                dataType
                options { id name }
              }
              ... on ProjectV2IterationField {
                id
                name
                dataType
              }
            }
          }
        }
      }
    }
    """
    fields: list[dict[str, Any]] = []
    after = None
    while True:
        data = graphql_request(session, query, {"projectId": project_id, "after": after})
        node = data["node"]
        field_connection = node["fields"]
        fields.extend(field_connection["nodes"])
        if not field_connection["pageInfo"]["hasNextPage"]:
            return fields
        after = field_connection["pageInfo"]["endCursor"]


def ensure_field_type(name: str, existing: dict[str, Any], desired: dict[str, Any]) -> None:
    existing_data_type = existing.get("dataType")
    if existing_data_type is None:
        raise ApplyFailure(f"project field '{name}' exists but does not expose a supported data type")
    existing_type = github_field_type(existing_data_type)
    if existing_type != desired["type"]:
        raise ApplyFailure(
            f"project field '{name}' exists with type '{existing_type}', expected '{desired['type']}'"
        )


def github_field_type(data_type: str) -> str:
    mapping = {
        "TEXT": "text",
        "NUMBER": "number",
        "DATE": "date",
        "SINGLE_SELECT": "single_select",
    }
    return mapping.get(data_type, data_type.lower())


def create_project_field(
    session: requests.Session, project_id: str, field: dict[str, Any]
) -> dict[str, Any]:
    mutation = """
    mutation($input: CreateProjectV2FieldInput!) {
      createProjectV2Field(input: $input) {
        projectV2Field {
          ... on ProjectV2Field {
            id
            name
            dataType
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            dataType
            options { id name }
          }
        }
      }
    }
    """
    mutation_input: dict[str, Any] = {
        "projectId": project_id,
        "dataType": field["type"].upper(),
        "name": field["name"],
    }
    if field["type"] == "single_select":
        mutation_input["singleSelectOptions"] = single_select_options_input(field)

    data = graphql_request(
        session,
        mutation,
        {"input": mutation_input},
    )
    return data["createProjectV2Field"]["projectV2Field"]


def sync_single_select_options(
    session: requests.Session, existing: dict[str, Any], desired: dict[str, Any]
) -> None:
    existing_options = {option["name"]: option for option in existing.get("options", [])}
    desired_option_names = [
        option["name"] if isinstance(option, dict) else option for option in desired.get("options", [])
    ]
    if all(option_name in existing_options for option_name in desired_option_names):
        return
    print(f"Updating options for project field: {desired['name']}")
    update_single_select_field(session, existing["id"], desired)


def update_single_select_field(
    session: requests.Session, field_id: str, desired: dict[str, Any]
) -> None:
    mutation = """
    mutation($input: UpdateProjectV2FieldInput!) {
      updateProjectV2Field(input: $input) {
        projectV2Field {
          ... on ProjectV2SingleSelectField {
            id
            name
            dataType
            options { id name }
          }
        }
      }
    }
    """
    graphql_request(
        session,
        mutation,
        {
            "input": {
                "fieldId": field_id,
                "name": desired["name"],
                "singleSelectOptions": single_select_options_input(desired),
            }
        },
    )


def single_select_options_input(field: dict[str, Any]) -> list[dict[str, str]]:
    options = []
    for option in field.get("options", []):
        if isinstance(option, str):
            options.append({"name": option, "color": "GRAY", "description": ""})
        else:
            options.append(
                {
                    "name": option["name"],
                    "color": option.get("color", "GRAY").upper(),
                    "description": option.get("description", ""),
                }
            )
    return options


def collect_issues(config: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for issue in config.get("issues", []):
        add_issue_tree(issues, issue)
    for phase in config.get("roadmap", []):
        for epic in phase.get("epics", []):
            issue = dict(epic)
            issue.setdefault("milestone", phase.get("milestone"))
            add_issue_tree(issues, issue)
    return issues


def add_issue_tree(
    issues: list[dict[str, Any]], issue: dict[str, Any], inherited_milestone: str | None = None
) -> None:
    issue_copy = dict(issue)
    sub_issues = issue_copy.get("sub_issues", []) or []
    if inherited_milestone and not issue_copy.get("milestone"):
        issue_copy["milestone"] = inherited_milestone
    issues.append(issue_copy)

    child_milestone = issue_copy.get("milestone")
    for sub_issue in sub_issues:
        add_issue_tree(issues, sub_issue, child_milestone)


def sync_issues(
    session: requests.Session,
    owner: str,
    repo: str,
    issues: list[dict[str, Any]],
    milestone_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    existing_issues = get_existing_issues_by_title(session, owner, repo)
    issue_nodes: dict[str, dict[str, Any]] = {}

    for issue in issues:
        title = issue["title"]
        existing = existing_issues.get(title)
        payload = issue_payload(issue, milestone_map)
        if existing is None:
            print(f"Creating issue: {title}")
            existing = rest_request(
                session,
                "POST",
                f"/repos/{owner}/{repo}/issues",
                expected_statuses={201},
                json=payload,
            )
        else:
            update_payload = dict(payload)
            update_payload["state"] = "closed" if issue.get("closed") else "open"
            if issue_needs_update(existing, update_payload):
                print(f"Updating issue: {title}")
                existing = rest_request(
                    session,
                    "PATCH",
                    f"/repos/{owner}/{repo}/issues/{existing['number']}",
                    expected_statuses={200},
                    json=update_payload,
                )

        issue_nodes[title] = existing

    return issue_nodes


def sync_sub_issues(
    session: requests.Session,
    owner: str,
    repo: str,
    issues: list[dict[str, Any]],
    issue_nodes: dict[str, dict[str, Any]],
) -> None:
    for parent_issue in issues:
        for child_issue in parent_issue.get("sub_issues", []) or []:
            parent_node = issue_nodes[parent_issue["title"]]
            child_node = issue_nodes[child_issue["title"]]
            ensure_sub_issue(session, owner, repo, parent_node, child_node)


def ensure_sub_issue(
    session: requests.Session,
    owner: str,
    repo: str,
    parent_issue: dict[str, Any],
    child_issue: dict[str, Any],
) -> None:
    existing_sub_issues = get_all_pages(
        session,
        f"/repos/{owner}/{repo}/issues/{parent_issue['number']}/sub_issues",
    )
    if any(sub_issue["id"] == child_issue["id"] for sub_issue in existing_sub_issues):
        return

    print(f"Adding sub-issue '{child_issue['title']}' to issue: {parent_issue['title']}")
    rest_request(
        session,
        "POST",
        f"/repos/{owner}/{repo}/issues/{parent_issue['number']}/sub_issues",
        expected_statuses={201},
        json={"sub_issue_id": child_issue["id"], "replace_parent": True},
    )


def get_existing_issues_by_title(
    session: requests.Session, owner: str, repo: str
) -> dict[str, dict[str, Any]]:
    items = get_all_pages(session, f"/repos/{owner}/{repo}/issues", {"state": "all"})
    issues = [item for item in items if "pull_request" not in item]
    return {issue["title"]: issue for issue in issues}


def issue_payload(
    issue: dict[str, Any], milestone_map: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": issue["title"],
        "body": issue.get("body", ""),
        "labels": issue.get("labels", []),
    }
    milestone = issue.get("milestone")
    if milestone:
        payload["milestone"] = milestone_map[milestone]["number"]
    return payload


def issue_needs_update(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    if existing.get("body") != desired.get("body"):
        return True
    if sorted(label["name"] for label in existing.get("labels", [])) != sorted(
        desired.get("labels", [])
    ):
        return True
    existing_milestone = existing.get("milestone")
    desired_milestone = desired.get("milestone")
    if (existing_milestone or {}).get("number") != desired_milestone:
        return True
    if existing.get("state") != desired.get("state"):
        return True
    return False


def sync_project_items(
    session: requests.Session,
    project_id: str,
    project_fields: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    issue_nodes: dict[str, dict[str, Any]],
) -> None:
    project_items = get_project_items(session, project_id)
    items_by_content_id = {
        item["content"]["id"]: item
        for item in project_items
        if item.get("content") and item["content"].get("id")
    }

    for issue in issues:
        issue_node = issue_nodes[issue["title"]]
        item = items_by_content_id.get(issue_node["node_id"])
        if item is None:
            print(f"Adding issue to project: {issue['title']}")
            item = add_project_item(session, project_id, issue_node["node_id"])
        sync_issue_field_values(session, project_id, item["id"], project_fields, issue)


def get_project_items(session: requests.Session, project_id: str) -> list[dict[str, Any]]:
    query = """
    query($projectId: ID!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              content {
                ... on Issue { id title number }
              }
            }
          }
        }
      }
    }
    """
    items: list[dict[str, Any]] = []
    after = None
    while True:
        data = graphql_request(session, query, {"projectId": project_id, "after": after})
        item_connection = data["node"]["items"]
        items.extend(item_connection["nodes"])
        if not item_connection["pageInfo"]["hasNextPage"]:
            return items
        after = item_connection["pageInfo"]["endCursor"]


def add_project_item(session: requests.Session, project_id: str, content_id: str) -> dict[str, Any]:
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    data = graphql_request(session, mutation, {"projectId": project_id, "contentId": content_id})
    return data["addProjectV2ItemById"]["item"]


def sync_issue_field_values(
    session: requests.Session,
    project_id: str,
    item_id: str,
    project_fields: dict[str, dict[str, Any]],
    issue: dict[str, Any],
) -> None:
    for field_name, value in (issue.get("fields", {}) or {}).items():
        field = project_fields[field_name]
        field_type = github_field_type(field["dataType"])
        print(f"Setting field '{field_name}' for issue: {issue['title']}")
        update_project_field_value(session, project_id, item_id, field, field_type, value)


def update_project_field_value(
    session: requests.Session,
    project_id: str,
    item_id: str,
    field: dict[str, Any],
    field_type: str,
    value: Any,
) -> None:
    if field_type == "single_select":
        option_id = find_option_id(field, value)
        field_value = {"singleSelectOptionId": option_id}
    elif field_type == "text":
        field_value = {"text": str(value)}
    elif field_type == "number":
        field_value = {"number": float(value)}
    elif field_type == "date":
        field_value = {"date": str(value)}
    else:
        raise ApplyFailure(f"unsupported project field type: {field_type}")

    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
      updateProjectV2ItemFieldValue(
        input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
      ) {
        projectV2Item { id }
      }
    }
    """
    graphql_request(
        session,
        mutation,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field["id"],
            "value": field_value,
        },
    )


def find_option_id(field: dict[str, Any], value: Any) -> str:
    for option in field.get("options", []):
        if option["name"] == value:
            return option["id"]
    raise ApplyFailure(f"option '{value}' not found for project field '{field['name']}'")


if __name__ == "__main__":
    sys.exit(main())
