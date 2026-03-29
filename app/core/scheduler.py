import logging
from datetime import UTC, date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.db import engine
from app.models import CalendarCategory, CalendarEvent, CalendarItem, PantryItem
from app.services.calendar_hub import list_due_reminders, sync_generated_calendar_items
from app.services.notifications import build_hub_link, send_push_notification
from app.services.scraper_service import run_intermarche_scraper

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _calendar_tags(category: CalendarCategory) -> list[str]:
    if category == CalendarCategory.TASK:
        return ["memo", "hourglass_flowing_sand"]
    if category == CalendarCategory.EVENT:
        return ["calendar", "round_pushpin"]
    if category == CalendarCategory.SUBSCRIPTION:
        return ["moneybag", "credit_card"]
    if category == CalendarCategory.MEAL:
        return ["fork_and_knife", "tomato"]
    return ["bell"]


async def check_expiring_pantry_items() -> None:
    """Daily check for items expiring in <= 3 days."""
    logger.info("Running daily check for expiring pantry items...")
    today = date.today()
    threshold = today + timedelta(days=3)

    with Session(engine) as session:
        statement = select(PantryItem).where(
            PantryItem.expires_at.is_not(None),
            PantryItem.expires_at <= threshold,
        )
        items = session.exec(statement).all()

        for item in items:
            days_left = (item.expires_at - today).days
            if days_left < 0:
                title = f"Product expired: {item.name}"
                message = f"{item.name} expired {-days_left} day(s) ago."
                priority = 4
                tags = ["rotating_light", "wastebasket"]
            elif days_left == 0:
                title = f"Expires today: {item.name}"
                message = f"{item.name} expires today."
                priority = 4
                tags = ["warning", "tomato"]
            else:
                title = f"Expiring soon: {item.name}"
                message = f"{item.name} expires in {days_left} day(s)."
                priority = 3
                tags = ["hourglass", "apple"]

            click = build_hub_link("/pantry", item=item.id)
            await send_push_notification(title, message, priority=priority, tags=tags, click=click)


async def check_upcoming_events() -> None:
    """Morning digest for calendar events happening today."""
    logger.info("Running daily check for upcoming events...")
    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    with Session(engine) as session:
        statement = select(CalendarEvent).where(
            CalendarEvent.start_at >= today_start,
            CalendarEvent.start_at < today_end,
        )
        events = session.exec(statement).all()

        for event in events:
            time_str = "all day" if event.all_day else event.start_at.astimezone(timezone.utc).strftime("%H:%M UTC")
            title = f"Event today: {event.title}"
            message = f"Starts at {time_str}. Location: {event.location or 'n/a'}"
            click = build_hub_link("/calendar", day=event.start_at.date().isoformat())
            await send_push_notification(title, message, priority=3, tags=["calendar", "round_pushpin"], click=click)


async def send_due_calendar_reminders(within_minutes: int = 20) -> None:
    """Dispatch due reminders for all calendar-linked domains."""
    logger.info("Running due calendar reminders check...")
    now = datetime.now(UTC)

    with Session(engine) as session:
        sync_generated_calendar_items(session)
        reminders = list_due_reminders(session, within_minutes=within_minutes)

        for reminder in reminders:
            item = reminder.item
            start_at = _as_utc(item.start_at)
            due_in = int((start_at - now).total_seconds() // 60)
            due_label = "now" if due_in <= 0 else f"in {due_in} min"
            start_local = start_at.strftime("%Y-%m-%d %H:%M UTC")

            click = build_hub_link(
                "/calendar",
                day=start_at.date().isoformat(),
                item=item.id,
            )
            sent = await send_push_notification(
                title=f"Reminder: {item.title}",
                message=f"{item.category.value} at {start_local} ({due_label})",
                priority=3,
                tags=_calendar_tags(item.category),
                click=click,
            )
            if not sent:
                continue

            db_item = session.get(CalendarItem, item.id)
            if db_item is None:
                continue
            db_item.last_notified_at = datetime.now(UTC)
            db_item.updated_at = datetime.now(UTC)
            session.add(db_item)

        session.commit()


async def scrape_grocery_catalog_job() -> None:
    """Daily progressive scrape of the supermarket catalog."""
    logger.info("Running progressive grocery catalog scrape...")
    
    # Generic keywords to scrape periodically to build up a catalog
    keywords = ["lait", "oeufs", "beurre", "pain", "eau", "fromage", "poulet", "viande", "pâtes", "riz", "tomates", "pommes", "bananes"]
    
    # We could rotate through the keywords here, but for now we scrape them all.
    with Session(engine) as session:
        try:
            await run_intermarche_scraper(session, queries=keywords, max_results=5)
            logger.info("Progressive grocery catalog scrape completed.")
        except Exception as e:
            logger.error(f"Failed progressive grocery catalog scrape: {e}")


def setup_scheduler() -> None:
    """Configure and start the background scheduler."""
    scheduler.add_job(
        check_expiring_pantry_items,
        CronTrigger(hour=9, minute=0),
        id="check_pantry_expiry",
        replace_existing=True,
    )

    scheduler.add_job(
        check_upcoming_events,
        CronTrigger(hour=8, minute=0),
        id="check_upcoming_events",
        replace_existing=True,
    )

    scheduler.add_job(
        send_due_calendar_reminders,
        CronTrigger(minute="*/5"),
        id="check_calendar_due_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        scrape_grocery_catalog_job,
        CronTrigger(hour=3, minute=0),  # Run at 3 AM
        id="scrape_grocery_catalog",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Background scheduler started successfully with pantry/event/reminder jobs.")


def shutdown_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler shut down successfully.")
