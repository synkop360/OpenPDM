from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_persists_immutable_plugin_packages() -> None:
    configuration = yaml.safe_load((ROOT / "deployment" / "compose.yaml").read_text())
    backend = configuration["services"]["backend"]

    assert backend["environment"]["OPENPDM_PLUGIN_PACKAGE_ROOT"] == "/var/lib/openpdm/plugins"
    assert "plugin-packages:/var/lib/openpdm/plugins" in backend["volumes"]
    assert "plugin-packages" in configuration["volumes"]
