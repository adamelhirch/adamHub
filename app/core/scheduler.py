import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.db import engine
from app.models import CalendarEvent, PantryItem
from app.services.notifications import send_push_notification

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()

async def check_expiring_pantry_items():
    """Daily check for items expiring in <= 3 days."""
    logger.info("Running daily check for expiring pantry items...")
    today = date.today()
    threshold = today + timedelta(days=3)
    
    with Session(engine) as session:
        statement = select(PantryItem).where(
            PantryItem.expires_at.is_not(None), 
            PantryItem.expires_at <= threshold
        )
        items = session.exec(statement).all()
        
        for item in items:
            days_left = (item.expires_at - today).days
            if days_left < 0:
                title = f"⚠️ Terminé: {item.name}"
                msg = f"Votre produit {item.name} est expiré depuis {-days_left} jours !"
                priority = 4
                tags = ["rotating_light", "wastebasket"]
            elif days_left == 0:
                title = f"🚨 Expire aujourd'hui: {item.name}"
                msg = f"Attention, votre produit {item.name} expire aujourd'hui."
                priority = 4
                tags = ["warning", "tomato"]
            else:
                title = f"⏳ Bientôt expiré: {item.name}"
                msg = f"Votre produit {item.name} expire dans {days_left} jours."
                priority = 3
                tags = ["hourglass", "apple"]
                
            await send_push_notification(title, msg, priority, tags)

async def check_upcoming_events():
    """Daily check for Calendar events happening today."""
    logger.info("Running daily check for upcoming events...")
    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    
    with Session(engine) as session:
        statement = select(CalendarEvent).where(
            CalendarEvent.start_at >= today_start,
            CalendarEvent.start_at < today_end
        )
        events = session.exec(statement).all()
        
        for event in events:
            time_str = "Toute la journée" if event.all_day else event.start_at.strftime("%H:%M")
            title = f"📅 Événement: {event.title}"
            msg = f"Prévu aujourd'hui à {time_str}.\nLieu: {event.location or 'Non précisé'}"
            await send_push_notification(title, msg, priority=3, tags=["calendar", "round_pushpin"])

def setup_scheduler():
    """Configure and start the background scheduler."""
    # Add jobs - adjusting cron times based on preference
    # E.g., run every day at 09:00 AM
    scheduler.add_job(
        check_expiring_pantry_items, 
        CronTrigger(hour=9, minute=0),
        id="check_pantry_expiry",
        replace_existing=True
    )
    
    # Run every day at 08:00 AM
    scheduler.add_job(
        check_upcoming_events, 
        CronTrigger(hour=8, minute=0),
        id="check_upcoming_events",
        replace_existing=True
    )
    
    # Also add a job that runs shortly after startup for testing
    from datetime import datetime, timedelta
    scheduler.add_job(
        check_expiring_pantry_items,
        "date",
        run_date=datetime.now() + timedelta(seconds=10),
        id="initial_pantry_check"
    )
    
    scheduler.start()
    logger.info("Background scheduler started successfully with 2 daily jobs.")

def shutdown_scheduler():
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler shut down successfully.")
