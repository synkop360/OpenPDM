"""Request-scoped observability context shared by Platform Modules."""

from contextvars import ContextVar

CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar("openpdm_request_id", default=None)


def set_request_id(value: str | None) -> object:
    return CURRENT_REQUEST_ID.set(value)


def reset_request_id(token: object) -> None:
    CURRENT_REQUEST_ID.reset(token)  # type: ignore[arg-type]


def get_request_id() -> str | None:
    return CURRENT_REQUEST_ID.get()
