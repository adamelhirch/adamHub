from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.core.crypto import decrypt_text, encrypt_text
from app.models import SupermarketConnection, SupermarketStore


def list_connections(
    session: Session,
    store: SupermarketStore | None = None,
    user_id: int | None = None,
) -> list[SupermarketConnection]:
    """List connections, scoped to a user or to the shared legacy ones.

    `user_id` selects the caller's own connections. When it is None, only the
    pre-scoping shared connections (user_id IS NULL) are returned — callers use
    this to surface the legacy single-user rows to the owner.
    """
    statement = select(SupermarketConnection).order_by(
        SupermarketConnection.is_active.desc(),
        SupermarketConnection.updated_at.desc(),
    )
    if store is not None:
        statement = statement.where(SupermarketConnection.store == store)
    if user_id is not None:
        statement = statement.where(SupermarketConnection.user_id == user_id)
    else:
        statement = statement.where(SupermarketConnection.user_id.is_(None))
    return list(session.exec(statement).all())


def get_connection(session: Session, connection_id: int) -> SupermarketConnection | None:
    return session.get(SupermarketConnection, connection_id)


def get_active_connection(
    session: Session,
    store: SupermarketStore,
    user_id: int | None = None,
) -> SupermarketConnection | None:
    """Return the active connection for a store, scoped like `list_connections`.

    `user_id` selects the caller's own active connection; None looks up the
    shared legacy connection (user_id IS NULL).
    """
    statement = select(SupermarketConnection).where(
        SupermarketConnection.store == store,
        SupermarketConnection.is_active.is_(True),
    )
    if user_id is not None:
        statement = statement.where(SupermarketConnection.user_id == user_id)
    else:
        statement = statement.where(SupermarketConnection.user_id.is_(None))
    return session.exec(statement).first()


def upsert_connection(
    session: Session,
    *,
    store: SupermarketStore,
    label: str,
    cookies: list[dict[str, Any]],
    credentials: dict[str, Any] | None = None,
    activate: bool = True,
    connection_id: int | None = None,
    user_id: int | None = None,
    customer_uuid: str | None = None,
) -> SupermarketConnection:
    """Create or update a connection, optionally making it active for its store.

    When a `user_id` is provided, the connection is scoped to that user — both
    deduplication (by store+label) and the "deactivate others" toggle stay
    within that user's connections.

    `cookies_encrypted` stays the single at-rest container: it holds either the
    raw JSON cookie list (legacy format, backward compatible) or, when `cookies`
    is empty and `credentials` is given, a `{"type": "credentials", ...}` dict.
    Credentials are a best-effort fallback — the extension cookie path remains
    the reliable one.

    `customer_uuid` (Intermarché) is stored separately from the cookies blob:
    when omitted, a previously stored value is left untouched rather than
    cleared, so a routine cookie-only re-sync from the extension doesn't wipe
    it (it is never present in the cookies themselves).
    """
    now = datetime.now(UTC)
    if cookies:
        plain_payload: Any = cookies
    elif credentials:
        plain_payload = {"type": "credentials", "credentials": credentials}
    else:
        raise ValueError("cookies or credentials are required")
    payload = encrypt_text(json.dumps(plain_payload, ensure_ascii=False))

    existing: SupermarketConnection | None = None
    if connection_id is not None:
        existing = get_connection(session, connection_id)
        if existing is None or existing.store != store:
            raise ValueError("Connection not found for this store")
        if user_id is not None and existing.user_id not in (None, user_id):
            raise ValueError("Connection belongs to another user")
    else:
        # Match by (user_id, store, label) for idempotency.
        statement = select(SupermarketConnection).where(
            SupermarketConnection.store == store,
            SupermarketConnection.label == label,
        )
        if user_id is not None:
            statement = statement.where(SupermarketConnection.user_id == user_id)
        else:
            statement = statement.where(SupermarketConnection.user_id.is_(None))
        existing = session.exec(statement).first()

    if existing is not None:
        existing.label = label
        existing.cookies_encrypted = payload
        existing.updated_at = now
        if user_id is not None:
            existing.user_id = user_id
        if customer_uuid is not None:
            existing.customer_uuid = customer_uuid
        if activate:
            _deactivate_others(session, store, exclude_id=existing.id, now=now, user_id=user_id)
            existing.is_active = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    if activate:
        _deactivate_others(session, store, exclude_id=None, now=now, user_id=user_id)

    connection = SupermarketConnection(
        store=store,
        label=label.strip() or f"{store.value}-connection",
        cookies_encrypted=payload,
        is_active=activate,
        user_id=user_id,
        customer_uuid=customer_uuid,
        created_at=now,
        updated_at=now,
    )
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


def activate_connection(
    session: Session, connection_id: int, *, user_id: int | None = None
) -> SupermarketConnection | None:
    connection = get_connection(session, connection_id)
    if connection is None:
        return None
    now = datetime.now(UTC)
    _deactivate_others(session, connection.store, exclude_id=connection.id, now=now, user_id=user_id)
    connection.is_active = True
    connection.updated_at = now
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


def delete_connection(
    session: Session, connection_id: int, *, user_id: int | None = None
) -> SupermarketConnection | None:
    del user_id  # reserved for ownership checks performed by the caller
    connection = get_connection(session, connection_id)
    if connection is None:
        return None
    session.delete(connection)
    session.commit()
    return connection


def _deactivate_others(
    session: Session,
    store: SupermarketStore,
    *,
    exclude_id: int | None,
    now: datetime,
    user_id: int | None = None,
) -> None:
    statement = select(SupermarketConnection).where(
        SupermarketConnection.store == store,
        SupermarketConnection.is_active.is_(True),
    )
    if user_id is not None:
        statement = statement.where(SupermarketConnection.user_id == user_id)
    else:
        statement = statement.where(SupermarketConnection.user_id.is_(None))
    for other in session.exec(statement).all():
        if other.id == exclude_id:
            continue
        other.is_active = False
        other.updated_at = now
        session.add(other)


def decrypt_cookies(connection: SupermarketConnection) -> list[dict[str, Any]]:
    raw = decrypt_text(connection.cookies_encrypted)
    parsed = json.loads(raw)
    return list(parsed) if isinstance(parsed, list) else []


def decrypt_credentials(connection: SupermarketConnection) -> dict[str, Any] | None:
    """Return the stored credentials dict, or None when the container holds cookies."""
    raw = decrypt_text(connection.cookies_encrypted)
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and parsed.get("type") == "credentials":
        return parsed.get("credentials")
    return None


def touch_connection(session: Session, connection: SupermarketConnection) -> None:
    """Update last_used_at on a connection (best-effort, swallows errors)."""
    try:
        connection.last_used_at = datetime.now(UTC)
        session.add(connection)
        session.commit()
    except Exception:
        session.rollback()
