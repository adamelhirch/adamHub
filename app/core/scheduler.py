import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.db import engine
from app.models import PantryItem
from app.services.notifications import build_hub_link, send_push_notification
from app.services.store_catalog import run_intermarche_scraper

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


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
                title = f"Produit périmé : {item.name}"
                message = f"{item.name} a expiré il y a {-days_left} jour(s)."
                priority = 4
                tags = ["rotating_light", "wastebasket"]
            elif days_left == 0:
                title = f"Périme aujourd'hui : {item.name}"
                message = f"{item.name} expire aujourd'hui."
                priority = 4
                tags = ["warning", "tomato"]
            else:
                title = f"Périme bientôt : {item.name}"
                message = f"{item.name} expire dans {days_left} jour(s)."
                priority = 3
                tags = ["hourglass", "apple"]

            click = build_hub_link("/pantry", item=item.id)
            await send_push_notification(title, message, priority=priority, tags=tags, click=click)


async def scrape_grocery_catalog_job() -> None:
    """Daily progressive scrape of the supermarket catalog."""
    logger.info("Running progressive grocery catalog scrape...")
    keywords = ["lait", "oeufs", "beurre", "pain", "eau", "fromage", "poulet", "viande", "pâtes", "riz", "tomates", "pommes", "bananes"]
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
        scrape_grocery_catalog_job,
        CronTrigger(hour=3, minute=0),  # Run at 3 AM
        id="scrape_grocery_catalog",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Background scheduler started with pantry expiry and grocery catalog scrape jobs.")


def shutdown_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler shut down successfully.")
