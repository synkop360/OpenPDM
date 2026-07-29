"""Public Assets Platform Module contract."""

from typing import Any, Protocol


class AssetsInterface(Protocol):
    """Own the Asset, Revision, and Representation lifecycle."""

    def require_asset_permission(
        self, db: Any, *, asset_id: str, actor: Any, permission: str
    ) -> Any: ...

    def get_representation_for_analysis(
        self, db: Any, *, representation_id: str, actor: Any
    ) -> tuple[Any, Any]: ...
