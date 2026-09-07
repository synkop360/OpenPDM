from __future__ import annotations

import importlib.util
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("deployments", ROOT / "scripts" / "deployments.py")
assert spec is not None and spec.loader is not None
deployments = importlib.util.module_from_spec(spec)
sys.modules["deployments"] = deployments
spec.loader.exec_module(deployments)


@pytest.fixture
def deployments_dir(tmp_path, monkeypatch):
    target = tmp_path / "deployments"
    monkeypatch.setattr(deployments, "DEPLOYMENTS_DIR", target)
    return target


def test_slugify_normalises_free_text() -> None:
    assert deployments.slugify("  My Test Org! ") == "my-test-org"
    assert deployments.slugify("acme_prod") == "acme-prod"


def test_slugify_rejects_empty_and_reserved() -> None:
    for bad in ("", "!!", "x", "default", "a" * 60):
        with pytest.raises(deployments.DeploymentError):
            deployments.slugify(bad)


def test_default_deployment_matches_historical_stack() -> None:
    default = deployments.default_deployment()
    assert default.is_default
    assert default.compose_project == "deployment"
    assert default.backend_host_port == 18000
    assert default.backend_url == "http://localhost:18000"
    assert default.compose_base_args()[:1] != ["-p"]  # default is unprefixed


def test_named_deployment_compose_args_are_project_scoped(deployments_dir) -> None:
    dep = deployments.create("acme", deployments.StorageConfig(kind="bundled"))
    args = dep.compose_base_args()
    assert args[:2] == ["-p", "openpdm-acme"]
    assert "--env-file" in args


def test_find_free_port_skips_bound_and_reserved() -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = taken.getsockname()[1]
        chosen = deployments.find_free_port(taken_port, reserved={taken_port + 1})
        assert chosen >= taken_port
        assert chosen not in (taken_port, taken_port + 1)


def test_create_allocates_nonoverlapping_blocks(deployments_dir) -> None:
    first = deployments.create("one", deployments.StorageConfig(kind="bundled"))
    second = deployments.create("two", deployments.StorageConfig(kind="bundled"))

    assert first.backend_host_port == 18010
    assert second.backend_host_port == 18020
    assert first.frontend_host_port == 5183
    assert second.frontend_host_port == 5193
    assert {first.pg_host_port, second.pg_host_port} == {5442, 5452}
    assert first.env_file.exists() and second.env_file.exists()


def test_default_deployment_frontend_port_is_5173() -> None:
    assert deployments.default_deployment().frontend_host_port == 5173
    assert deployments.default_deployment().frontend_url == "http://localhost:5173"


def test_frontend_host_port_roundtrips_through_the_env_file(deployments_dir) -> None:
    created = deployments.create("web", deployments.StorageConfig(kind="bundled"))
    assert deployments.load("web").frontend_host_port == created.frontend_host_port


def test_create_rejects_duplicates(deployments_dir) -> None:
    deployments.create("dup", deployments.StorageConfig(kind="bundled"))
    with pytest.raises(deployments.DeploymentError):
        deployments.create("dup", deployments.StorageConfig(kind="bundled"))


def test_load_roundtrips_s3_storage(deployments_dir) -> None:
    created = deployments.create(
        "ovh",
        deployments.StorageConfig(
            kind="s3",
            endpoint_url="https://s3.gra.io.cloud.ovh.net",
            region="gra",
            bucket="ovh-blobs",
            access_key="AK",
            secret_key="SK",
        ),
    )
    loaded = deployments.load("ovh")
    assert loaded.storage.kind == "s3"
    assert loaded.storage.endpoint_url == "https://s3.gra.io.cloud.ovh.net"
    assert loaded.storage.region == "gra"
    assert loaded.backend_host_port == created.backend_host_port
    assert loaded.compose_project == "openpdm-ovh"


def test_load_unknown_deployment_raises(deployments_dir) -> None:
    with pytest.raises(deployments.DeploymentError):
        deployments.load("does-not-exist")


def test_load_default_needs_no_file(deployments_dir) -> None:
    assert deployments.load("default").is_default


def test_local_storage_env_pairs_use_file_url() -> None:
    storage = deployments.StorageConfig(kind="local", local_source="openpdm-x-blobs")
    pairs = storage.env_pairs()
    assert pairs["OPENPDM_S3_ENDPOINT_URL"].startswith("file://")
    assert pairs["OPENPDM_BLOB_LOCAL_SOURCE"] == "openpdm-x-blobs"


def test_local_deployment_without_a_source_gets_its_own_volume(deployments_dir) -> None:
    dep = deployments.create("scratch", deployments.StorageConfig(kind="local", local_source=""))
    assert dep.storage.local_source == "openpdm-scratch-blobs"
    assert deployments.load("scratch").storage.local_source == "openpdm-scratch-blobs"


def test_local_deployment_keeps_an_explicit_host_path(deployments_dir) -> None:
    dep = deployments.create(
        "bind", deployments.StorageConfig(kind="local", local_source="/srv/openpdm/bind")
    )
    assert dep.storage.local_source == "/srv/openpdm/bind"


def test_list_deployment_names_ignores_example_and_default(deployments_dir) -> None:
    deployments_dir.mkdir(parents=True)
    (deployments_dir / "example.env").write_text("x=1", encoding="utf-8")
    (deployments_dir / "default.env").write_text("x=1", encoding="utf-8")
    deployments.create("real", deployments.StorageConfig(kind="bundled"))
    assert deployments.list_deployment_names() == ["real"]
