#!/usr/bin/env python3
"""OpenPDM Launcher: a small desktop GUI wrapper around start_all.py.

    uv run python scripts/launcher_gui.py

Uses only the Python standard library (tkinter), so it packages cleanly
with PyInstaller without pulling in a GUI toolkit dependency. This is the
intended PyInstaller entry point for a double-click launcher (see
docs/DEVELOPMENT.md).

Scope note: Docker Compose needs the real repository files on disk
(Dockerfiles, compose.yaml, package.json, the plugin sources...), so
packaging this as an .exe makes it a convenient launcher for an existing
OpenPDM checkout, not a self-contained distributable of the whole stack.

This file only adds a GUI driver on top of the orchestration already
implemented in start_all.py; it does not duplicate that logic. start_all.py
itself is unaffected and keeps working exactly as before (python
scripts/start_all.py, --dry-run, --skip-compose, --skip-frontend,
--skip-plugins).
"""

from __future__ import annotations

import argparse
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk
from typing import Any

VITE_LOCAL_URL_PATTERN = re.compile(r"Local:\s*(\S+)")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import start_all  # noqa: E402

# ---- Palette matching the OpenPDM Web UI dark theme ----
CANVAS = "#0d0f10"
PANEL = "#131517"
RAISED = "#1b1d1f"
BORDER = "#34383a"
TEXT = "#f3f5f4"
MUTED = "#a3aaa7"
ACCENT = "#4f8fe8"
ACCENT_HOVER = "#6ba2ee"
SUCCESS = "#50b68c"
WARNING = "#e8aa55"
DANGER = "#ef806f"

STATUS_COLORS = {
    "running": SUCCESS,
    "starting": WARNING,
    "restarting": WARNING,
    "paused": WARNING,
    "created": MUTED,
    "not created": MUTED,
    "exited": DANGER,
    "dead": DANGER,
    "not responding": DANGER,
    "unavailable": DANGER,
    "unknown": MUTED,
}

SERVICE_LABELS = [
    ("postgres", "PostgreSQL"),
    ("minio", "MinIO"),
    ("backend", "Backend API"),
    ("plugins", "Official Plugins"),
    ("frontend", "Web UI"),
]
SERVICE_LABEL_BY_KEY = dict(SERVICE_LABELS)

# How often to re-check whether the Docker Compose containers still exist and
# what state they're in, independent of the Start/Stop actions -- so a crash
# (e.g. a container exiting after startup) is noticed without the user having
# to click Start again. Configurable via --check-interval (seconds).
DEFAULT_CONTAINER_CHECK_INTERVAL_SECONDS = 300


def describe_container_state(service: str, state: str) -> str:
    """A clear, human-readable line for a Compose service's current container state."""
    label = SERVICE_LABEL_BY_KEY.get(service, service)
    if state == "running":
        return f"[OK] {label} container is running."
    if state == "not created":
        return f"{label} container does not exist yet."
    if state in ("exited", "dead"):
        return f"[FAIL] {label} container exists but is not running (state: {state})."
    return f"[WARN] {label} container state: {state}."


@dataclass
class GuiEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


class QueueStatusLine:
    """Duck-types start_all.StatusLine's interface, routing updates through the GUI queue."""

    def __init__(self, events: "queue.Queue[GuiEvent]") -> None:
        self._events = events

    def spin(self, text: str) -> None:
        self._events.put(GuiEvent("phase", {"text": text}))

    def ok(self, text: str) -> None:
        self._events.put(GuiEvent("log", {"text": f"[OK] {text}"}))

    def warn(self, text: str) -> None:
        self._events.put(GuiEvent("log", {"text": f"[WARN] {text}"}))

    def fail(self, text: str) -> None:
        self._events.put(GuiEvent("log", {"text": f"[FAIL] {text}"}))

    def info(self, text: str) -> None:
        self._events.put(GuiEvent("log", {"text": text}))


def spawn_captured(
    label: str,
    command: list[str],
    cwd: Path,
    events: "queue.Queue[GuiEvent]",
    *,
    debug: bool,
) -> subprocess.Popen[str]:
    """Start a process with its output streamed into the GUI's log instead of a new console.

    Docker Compose's own output ("docker messages") is useful to watch during a build --
    especially on a brand new install -- so it is always shown. The frontend dev server's
    command output is much noisier (dependency pre-bundling, HMR chatter) and rarely useful
    on its own, so by default only the Vite server address (and any error line) is surfaced;
    pass --debug to see everything raw, exactly as each process printed it.
    """
    dev_module = start_all.load_dev_module()
    env = dev_module.command_env()
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        # Docker Compose and Vite both emit UTF-8 (checkmarks, arrows, box
        # characters); without this, text=True falls back to the platform's
        # default encoding -- cp1252 on Windows -- which can't decode that
        # output and crashes this thread with a UnicodeDecodeError.
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    show_raw = debug or label == "compose"

    def pump() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            stripped = line.rstrip()
            if show_raw:
                events.put(GuiEvent("log", {"text": f"[{label}] {stripped}"}))
                continue
            url_match = VITE_LOCAL_URL_PATTERN.search(stripped)
            if url_match:
                events.put(
                    GuiEvent("log", {"text": f"[OK] Web UI available at {url_match.group(1)}"})
                )
            elif "error" in stripped.lower():
                events.put(GuiEvent("log", {"text": f"[{label}] {stripped}"}))
        exit_code = process.poll()
        if show_raw or exit_code != 0:
            events.put(GuiEvent("log", {"text": f"[{label}] process exited (code {exit_code})"}))

    threading.Thread(target=pump, daemon=True).start()
    return process


def run_startup_sequence(
    events: "queue.Queue[GuiEvent]", skip_plugins: bool, *, debug: bool
) -> list[tuple[str, subprocess.Popen[str]]]:
    """Run the same sequence as start_all.py's CLI mode, emitting GuiEvents instead of printing.

    Returns the (label, process) pairs this call itself started, so the GUI
    only ever stops what it started -- exactly like the CLI's behavior.
    """
    managed: list[tuple[str, subprocess.Popen[str]]] = []
    status = QueueStatusLine(events)

    events.put(GuiEvent("phase", {"text": "Checking Docker Compose services..."}))
    states = start_all.get_compose_service_states()
    for service in start_all.COMPOSE_SERVICES:
        events.put(
            GuiEvent(
                "service_status", {"service": service, "state": states.get(service, "not created")}
            )
        )

    already_running = all(
        states.get(service) == "running" for service in start_all.COMPOSE_SERVICES
    )
    if already_running:
        events.put(
            GuiEvent("log", {"text": "Compose stack is already running; not restarting it."})
        )
    else:
        events.put(GuiEvent("phase", {"text": "Starting the Compose stack..."}))
        process = spawn_captured(
            "compose",
            start_all.build_dev_helper_command("compose_up"),
            ROOT,
            events,
            debug=debug,
        )
        managed.append(("compose", process))

    healthy = start_all.wait_for_backend(
        f"{start_all.COMPOSE_BACKEND_URL}/health", timeout=300, status=status
    )
    if not healthy:
        events.put(GuiEvent("service_status", {"service": "backend", "state": "not responding"}))
        events.put(
            GuiEvent("error", {"text": "Backend did not become healthy within the timeout."})
        )
        return managed
    events.put(GuiEvent("service_status", {"service": "backend", "state": "running"}))

    if skip_plugins:
        events.put(GuiEvent("service_status", {"service": "plugins", "state": "skipped"}))
    else:
        start_all.ensure_default_plugins(status)
        events.put(GuiEvent("service_status", {"service": "plugins", "state": "running"}))

    frontend_command, frontend_available = start_all.resolve_frontend_runner()
    if not frontend_available:
        events.put(GuiEvent("service_status", {"service": "frontend", "state": "unavailable"}))
        events.put(
            GuiEvent(
                "log", {"text": "pnpm/npm not found on PATH; frontend dev server was not started."}
            )
        )
    else:
        events.put(GuiEvent("phase", {"text": "Starting the frontend dev server..."}))
        process = spawn_captured(
            "frontend",
            start_all.build_dev_helper_command(
                "run_javascript_script", ROOT / "frontend", runner_override=frontend_command[0]
            ),
            ROOT / "frontend",
            events,
            debug=debug,
        )
        managed.append(("frontend", process))
        frontend_ready = start_all.wait_for_backend(
            start_all.FRONTEND_URL, timeout=60, status=status
        )
        events.put(
            GuiEvent(
                "service_status",
                {"service": "frontend", "state": "running" if frontend_ready else "not responding"},
            )
        )

    events.put(GuiEvent("done", {}))
    return managed


class LauncherApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        debug: bool = False,
        check_interval_seconds: int = DEFAULT_CONTAINER_CHECK_INTERVAL_SECONDS,
    ) -> None:
        self.root = root
        self.debug = debug
        self.check_interval_seconds = check_interval_seconds
        self.events: "queue.Queue[GuiEvent]" = queue.Queue()
        self.managed_processes: list[tuple[str, subprocess.Popen[str]]] = []
        self.worker: threading.Thread | None = None
        self.service_state_labels: dict[str, ttk.Label] = {}
        self.service_dot_labels: dict[str, tk.Label] = {}
        self._last_container_states: dict[str, str] | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_events)
        self._run_container_check()
        self._schedule_next_container_check()

    # ---- UI construction ----

    def _build_ui(self) -> None:
        self.root.title("OpenPDM Launcher")
        self.root.geometry("720x560")
        self.root.minsize(600, 440)
        self.root.configure(bg=CANVAS)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=CANVAS)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=CANVAS, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure(
            "Heading.TLabel", background=CANVAS, foreground=TEXT, font=("Segoe UI", 15, "bold")
        )
        style.configure("Phase.TLabel", background=CANVAS, foreground=MUTED, font=("Segoe UI", 9))
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#08111f",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", BORDER)])
        style.configure(
            "Secondary.TButton",
            background=RAISED,
            foreground=TEXT,
            borderwidth=1,
            padding=(14, 8),
            font=("Segoe UI", 10),
        )
        style.map("Secondary.TButton", background=[("active", BORDER), ("disabled", RAISED)])

        header = ttk.Frame(self.root, padding=(20, 18, 20, 10))
        header.pack(fill="x")
        ttk.Label(header, text="OpenPDM", style="Heading.TLabel").pack(anchor="w")
        subtitle = "Local development stack launcher"
        if self.debug:
            subtitle += " (debug: showing raw command output)"
        ttk.Label(header, text=subtitle, style="Phase.TLabel").pack(anchor="w")

        status_panel = ttk.Frame(self.root, style="Panel.TFrame", padding=16)
        status_panel.pack(fill="x", padx=20, pady=(6, 10))
        for service, label in SERVICE_LABELS:
            row = tk.Frame(status_panel, bg=PANEL)
            row.pack(fill="x", pady=3)
            dot = tk.Label(row, text="●", bg=PANEL, fg=MUTED, font=("Segoe UI", 11))
            dot.pack(side="left", padx=(0, 8))
            ttk.Label(row, text=label, style="Panel.TLabel", width=16, anchor="w").pack(side="left")
            state_label = ttk.Label(row, text="not checked", style="Muted.TLabel", anchor="w")
            state_label.pack(side="left")
            self.service_dot_labels[service] = dot
            self.service_state_labels[service] = state_label

        self.phase_label = ttk.Label(self.root, text="Idle.", style="Phase.TLabel")
        self.phase_label.pack(fill="x", padx=24)

        button_row = ttk.Frame(self.root, padding=(20, 10, 20, 6))
        button_row.pack(fill="x")
        self.start_button = ttk.Button(
            button_row, text="Start", style="Accent.TButton", command=self._on_start
        )
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            button_row,
            text="Stop",
            style="Secondary.TButton",
            command=self._on_stop,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(
            button_row,
            text="Open Web UI",
            style="Secondary.TButton",
            command=lambda: webbrowser.open(start_all.FRONTEND_URL),
            state="disabled",
        )
        self.open_button.pack(side="left", padx=(8, 0))
        self.refresh_button = ttk.Button(
            button_row,
            text="Refresh Status",
            style="Secondary.TButton",
            command=self._run_container_check,
        )
        self.refresh_button.pack(side="right")

        log_frame = ttk.Frame(self.root, padding=(20, 4, 20, 20))
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ---- Event handling ----

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_service_state(self, service: str, state: str) -> None:
        dot = self.service_dot_labels.get(service)
        label = self.service_state_labels.get(service)
        if dot is None or label is None:
            return
        color = STATUS_COLORS.get(state, MUTED)
        dot.configure(fg=color)
        label.configure(text=state)
        if service == "frontend" and state == "running":
            self.open_button.configure(state="normal")

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event.kind == "log":
                    self._append_log(event.data["text"])
                elif event.kind == "phase":
                    self.phase_label.configure(text=event.data["text"])
                    self._append_log(event.data["text"])
                elif event.kind == "service_status":
                    self._set_service_state(event.data["service"], event.data["state"])
                elif event.kind == "error":
                    self.phase_label.configure(text=event.data["text"])
                    self._append_log(f"[FAIL] {event.data['text']}")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="normal")
                elif event.kind == "done":
                    self.phase_label.configure(text="All services running.")
                    self.stop_button.configure(state="normal")
                elif event.kind == "container_check":
                    self._handle_container_check(event.data["states"])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle_container_check(self, states: dict[str, str]) -> None:
        """Update service dots and log a clear line for anything new or changed.

        Runs on the first check (always logs every container's state, so the
        user gets an unambiguous "exists or not" answer right at startup) and
        on every periodic re-check afterward (only logs services whose state
        actually changed, so a long-running session doesn't get spammed).
        """
        first_check = self._last_container_states is None
        previous = self._last_container_states or {}
        for service in start_all.COMPOSE_SERVICES:
            state = states.get(service, "not created")
            self._set_service_state(service, state)
            if first_check or previous.get(service) != state:
                self._append_log(describe_container_state(service, state))
        self._last_container_states = {
            service: states.get(service, "not created") for service in start_all.COMPOSE_SERVICES
        }

    # ---- Container check (initial, periodic and manual refresh) ----

    def _run_container_check(self) -> None:
        """Check container state in the background right now.

        Used for the initial check at startup, the periodic re-check, and
        the Refresh Status button -- a manual refresh doesn't touch the
        periodic timer, so it never stacks up extra recurring checks.
        """

        def check() -> None:
            states = start_all.get_compose_service_states()
            self.events.put(GuiEvent("container_check", {"states": states}))

        threading.Thread(target=check, daemon=True).start()

    def _schedule_next_container_check(self) -> None:
        self.root.after(self.check_interval_seconds * 1000, self._periodic_container_check)

    def _periodic_container_check(self) -> None:
        self._run_container_check()
        self._schedule_next_container_check()

    # ---- Actions ----

    def _on_start(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self._append_log("Starting OpenPDM...")

        def run() -> None:
            started = run_startup_sequence(self.events, skip_plugins=False, debug=self.debug)
            self.managed_processes = started

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def _on_stop(self) -> None:
        self.stop_button.configure(state="disabled")
        self._append_log("Stopping services started by this launcher...")
        for label, process in reversed(self.managed_processes):
            start_all.stop_process(process, label)
            if label == "compose":
                for service in start_all.COMPOSE_SERVICES:
                    self._set_service_state(service, "not created")
                self._set_service_state("plugins", "not created")
            else:
                self._set_service_state(label, "not created")
        self.managed_processes = []
        self.open_button.configure(state="disabled")
        self.start_button.configure(state="normal")
        self.phase_label.configure(text="Stopped.")

    def _on_close(self) -> None:
        if self.managed_processes:
            self._on_stop()
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenPDM desktop launcher.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show raw Docker Compose and Vite dev-server output in the log instead of just "
        "status messages, Docker messages and the Vite server address",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=DEFAULT_CONTAINER_CHECK_INTERVAL_SECONDS,
        metavar="SECONDS",
        help="How often to re-check whether the Docker containers still exist "
        f"(default: {DEFAULT_CONTAINER_CHECK_INTERVAL_SECONDS}s)",
    )
    return parser.parse_args()


def main(*, debug: bool | None = None, check_interval: int | None = None) -> int:
    if debug is None or check_interval is None:
        args = parse_args()
        debug = args.debug if debug is None else debug
        check_interval = args.check_interval if check_interval is None else check_interval
    root = tk.Tk()
    LauncherApp(root, debug=debug, check_interval_seconds=check_interval)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
