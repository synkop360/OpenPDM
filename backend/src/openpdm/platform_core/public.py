"""Public application-facing Platform Core value types."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class PlatformModule(Protocol):
    """Common structural contract implemented by every Platform Module facade."""


@dataclass(frozen=True, slots=True)
class SessionContextView:
    user: object
    session_token: object


@dataclass(frozen=True, slots=True)
class CollaborationStateView:
    asset: object
    state: str
    lock: object | None
    can_checkin: bool
    can_unlock: bool
    can_force_unlock: bool


@dataclass(frozen=True, slots=True)
class AssetLockSummaryView:
    """Lightweight collaboration-lock summary attached to an Asset in list views."""

    state: str
    owner_user_id: str | None
    owner_display_name: str | None
    locked_at: datetime | None
    is_mine: bool
    can_take_over: bool


@dataclass(frozen=True, slots=True)
class ActorLockView:
    """One collaboration lock held by the requesting user, with its Asset/Project context."""

    asset_id: str
    asset_name: str
    project_id: str
    project_name: str
    state: str
    locked_at: datetime


@dataclass(frozen=True, slots=True)
class TimelineEntryView:
    event_type: str
    occurred_at: datetime
    actor_user_id: str | None
    asset_id: str
    revision_id: str | None
    details: dict[str, object]


@dataclass(frozen=True, slots=True)
class GraphQueryResultView:
    root_asset: object
    direction: str
    max_depth: int
    target_asset_id: str | None
    path_exists: bool | None
    has_cycle: bool
    nodes: list[object]
    relationships: list[object]


@dataclass(frozen=True, slots=True)
class PluginEventDeliveryView:
    id: str
    plugin_id: str
    package_digest: str
    event_type: str
    payload: dict[str, object]
    attempt_count: int
