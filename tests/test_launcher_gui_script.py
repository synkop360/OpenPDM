from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("launcher_gui", ROOT / "scripts" / "launcher_gui.py")
assert spec is not None and spec.loader is not None
launcher_gui = importlib.util.module_from_spec(spec)
# launcher_gui.GuiEvent is a @dataclass; dataclass field resolution on some
# Python versions needs the module registered in sys.modules before exec.
sys.modules["launcher_gui"] = launcher_gui
spec.loader.exec_module(launcher_gui)


def test_describe_container_state_running() -> None:
    assert (
        launcher_gui.describe_container_state("postgres", "running")
        == "[OK] PostgreSQL container is running."
    )


def test_describe_container_state_not_created() -> None:
    assert (
        launcher_gui.describe_container_state("backend", "not created")
        == "Backend API container does not exist yet."
    )


def test_describe_container_state_exited_is_a_failure() -> None:
    message = launcher_gui.describe_container_state("backend", "exited")
    assert message.startswith("[FAIL]")
    assert "exited" in message


def test_describe_container_state_dead_is_a_failure() -> None:
    assert launcher_gui.describe_container_state("minio", "dead").startswith("[FAIL]")


def test_describe_container_state_other_states_are_warnings() -> None:
    assert launcher_gui.describe_container_state("minio", "restarting").startswith("[WARN]")


def test_status_colors_flag_exited_and_dead_as_danger() -> None:
    assert launcher_gui.STATUS_COLORS["exited"] == launcher_gui.DANGER
    assert launcher_gui.STATUS_COLORS["dead"] == launcher_gui.DANGER


def test_vite_local_url_pattern_extracts_address() -> None:
    line = "  ➜  Local:   http://localhost:5173/"
    match = launcher_gui.VITE_LOCAL_URL_PATTERN.search(line)
    assert match is not None
    assert match.group(1) == "http://localhost:5173/"


def test_default_check_interval_is_five_minutes() -> None:
    assert launcher_gui.DEFAULT_CONTAINER_CHECK_INTERVAL_SECONDS == 300
