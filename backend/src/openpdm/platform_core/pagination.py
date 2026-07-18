"""Opaque keyset pagination mechanics shared by Platform Modules."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import Session

T = TypeVar("T")


@dataclass(frozen=True)
class PageResult(Generic[T]):
    """A bounded page returned by an owning Platform Module."""

    items: list[T]
    next_cursor: str | None


def _encode_value(value: object) -> object:
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    return {"type": "scalar", "value": value}


def _decode_value(value: object) -> object:
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        raise ValueError("Invalid cursor value.")
    if value["type"] == "datetime" and isinstance(value["value"], str):
        return datetime.fromisoformat(value["value"])
    if value["type"] == "scalar":
        return value["value"]
    raise ValueError("Invalid cursor value.")


def encode_cursor(
    *, resource: str, scope: str, sort: str, direction: str, value: object, item_id: str
) -> str:
    payload = {
        "v": 1,
        "resource": resource,
        "scope": scope,
        "sort": sort,
        "direction": direction,
        "value": _encode_value(value),
        "id": item_id,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(
    *, cursor: str, resource: str, scope: str, sort: str, direction: str
) -> tuple[object, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if not isinstance(payload, dict):
            raise ValueError("Invalid cursor payload.")
        if (
            payload.get("v") != 1
            or payload.get("resource") != resource
            or payload.get("scope") != scope
            or payload.get("sort") != sort
            or payload.get("direction") != direction
            or not isinstance(payload.get("id"), str)
        ):
            raise ValueError("Cursor does not match this collection query.")
        return _decode_value(payload.get("value")), payload["id"]
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or incompatible page cursor.",
        ) from exc


def paginate(
    db: Session,
    *,
    statement: Select[Any],
    model: type[T],
    resource: str,
    scope: str,
    sort: str,
    direction: str,
    limit: int,
    cursor: str | None,
) -> PageResult[T]:
    """Apply stable composite keyset pagination to an authorized statement."""

    if direction not in {"asc", "desc"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sort direction."
        )
    sort_column = getattr(model, sort)
    id_column = model.id
    if cursor:
        value, item_id = decode_cursor(
            cursor=cursor,
            resource=resource,
            scope=scope,
            sort=sort,
            direction=direction,
        )
        comparison = sort_column > value if direction == "asc" else sort_column < value
        id_comparison = id_column > item_id if direction == "asc" else id_column < item_id
        statement = statement.where(or_(comparison, and_(sort_column == value, id_comparison)))
    order = sort_column.asc() if direction == "asc" else sort_column.desc()
    id_order = id_column.asc() if direction == "asc" else id_column.desc()
    rows = list(db.scalars(statement.order_by(order, id_order).limit(limit + 1)))
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(
            resource=resource,
            scope=scope,
            sort=sort,
            direction=direction,
            value=getattr(last, sort),
            item_id=str(last.id),
        )
    return PageResult(items=items, next_cursor=next_cursor)
