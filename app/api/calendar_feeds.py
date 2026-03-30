from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
import hashlib
import secrets
import unicodedata

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import PlainTextResponse
from sqlmodel import select

from app.api.calendar import list_calendar_items
from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.security import require_api_key
from app.models import CalendarFeed, CalendarSource
from app.schemas import CalendarFeedCreate, CalendarFeedRead
from app.services.calendar_hub import build_ics


private_router = APIRouter(
    prefix="/calendar/feeds",
    tags=["calendar-feeds"],
    dependencies=[Depends(require_api_key)],
)

public_router = APIRouter(tags=["calendar-feeds-public"])

FEED_LOOKBACK_DAYS = 30
FEED_LOOKAHEAD_DAYS = 365
FEED_ITEM_LIMIT = 5000


def _slugify_feed_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = "-".join(normalized.lower().split())
    safe = "".join(char for char in slug if char.isalnum() or char in {"-", "_"})
    return safe or "calendar-feed"


def _build_feed_urls(token: str) -> tuple[str, str]:
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    ics_url = f"{base}/calendar/feed/{token}.ics"
    if "://" in ics_url:
        scheme, rest = ics_url.split("://", 1)
        if scheme in {"http", "https"}:
            return ics_url, f"webcal://{rest}"
    return ics_url, ics_url


def _build_feed_read(feed: CalendarFeed) -> CalendarFeedRead:
    ics_url, webcal_url = _build_feed_urls(feed.token)
    return CalendarFeedRead(
        id=feed.id or 0,
        name=feed.name,
        token=feed.token,
        sources=[CalendarSource(value) for value in feed.sources or []],
        include_completed=feed.include_completed,
        active=feed.active,
        ics_url=ics_url,
        webcal_url=webcal_url,
        last_accessed_at=feed.last_accessed_at,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


def _generate_feed_token(session: SessionDep) -> str:
    while True:
        token = secrets.token_urlsafe(24)
        existing = session.exec(select(CalendarFeed).where(CalendarFeed.token == token)).first()
        if existing is None:
            return token


def _collect_feed_items(session: SessionDep, feed: CalendarFeed):
    now = datetime.now(UTC)
    from_at = now - timedelta(days=FEED_LOOKBACK_DAYS)
    to_at = now + timedelta(days=FEED_LOOKAHEAD_DAYS)
    items = list_calendar_items(
        session=session,
        from_at=from_at,
        to_at=to_at,
        include_completed=feed.include_completed,
        limit=FEED_ITEM_LIMIT,
    )
    if not feed.sources:
        return items
    allowed = set(feed.sources)
    return [
        item
        for item in items
        if (item.source.value if hasattr(item.source, "value") else str(item.source)) in allowed
    ]


@private_router.post("", response_model=CalendarFeedRead)
def create_calendar_feed(payload: CalendarFeedCreate, session: SessionDep) -> CalendarFeedRead:
    feed = CalendarFeed(
        name=payload.name,
        token=_generate_feed_token(session),
        sources=[source.value for source in payload.sources],
        include_completed=payload.include_completed,
    )
    session.add(feed)
    session.commit()
    session.refresh(feed)
    return _build_feed_read(feed)


@private_router.get("", response_model=list[CalendarFeedRead])
def list_calendar_feeds(session: SessionDep) -> list[CalendarFeedRead]:
    feeds = session.exec(select(CalendarFeed).order_by(CalendarFeed.created_at.desc())).all()
    return [_build_feed_read(feed) for feed in feeds if feed.active]


@private_router.delete("/{feed_id}")
def delete_calendar_feed(feed_id: int, session: SessionDep) -> dict:
    feed = session.get(CalendarFeed, feed_id)
    if not feed or not feed.active:
        raise HTTPException(status_code=404, detail="Calendar feed not found")
    session.delete(feed)
    session.commit()
    return {"ok": True, "deleted_id": feed_id}


@public_router.get("/calendar/feed/{token}.ics", response_class=PlainTextResponse)
def get_public_calendar_feed(
    token: str,
    session: SessionDep,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> Response:
    feed = session.exec(
        select(CalendarFeed).where(CalendarFeed.token == token, CalendarFeed.active.is_(True))
    ).first()
    if feed is None:
        raise HTTPException(status_code=404, detail="Calendar feed not found")

    items = _collect_feed_items(session, feed)
    ics_content = build_ics(items, calendar_name=feed.name)
    etag = hashlib.sha1(ics_content.encode("utf-8")).hexdigest()
    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304, headers={"ETag": f'"{etag}"'})

    now = datetime.now(UTC)
    feed.last_accessed_at = now
    feed.updated_at = feed.updated_at or now
    session.add(feed)
    session.commit()

    last_modified = max(
        [feed.updated_at, *(item.updated_at for item in items if getattr(item, "updated_at", None) is not None)],
        default=now,
    )
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=UTC)
    headers = {
        "Content-Disposition": f'inline; filename="{_slugify_feed_filename(feed.name)}.ics"',
        "Cache-Control": "no-cache",
        "ETag": f'"{etag}"',
        "Last-Modified": format_datetime(last_modified, usegmt=True),
        "X-Robots-Tag": "noindex",
    }
    return PlainTextResponse(ics_content, headers=headers, media_type="text/calendar")
