from datetime import datetime, timezone
import os
import time

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import GroceryItem, GroceryPantrySync, PantryItem


@pytest.mark.postgres
def test_postgres_fk_delete_smoke():
    db_url = os.getenv("ADAMHUB_POSTGRES_SMOKE_URL")
    if not db_url:
        pytest.skip("Set ADAMHUB_POSTGRES_SMOKE_URL to run postgres smoke tests")

    engine = create_engine(db_url, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    marker = f"pg-smoke-{int(time.time())}"
    with Session(engine) as session:
        pantry = PantryItem(name=f"{marker}-pantry", quantity=1, unit="item")
        grocery = GroceryItem(name=f"{marker}-grocery", quantity=1, unit="item", checked=True, priority=3)
        session.add(pantry)
        session.add(grocery)
        session.commit()
        session.refresh(pantry)
        session.refresh(grocery)

        sync = GroceryPantrySync(grocery_item_id=grocery.id, pantry_item_id=pantry.id, created_at=datetime.now(timezone.utc))
        session.add(sync)
        session.commit()

        linked = session.exec(select(GroceryPantrySync).where(GroceryPantrySync.pantry_item_id == pantry.id)).all()
        for row in linked:
            session.delete(row)
        session.commit()

        session.delete(pantry)
        session.delete(grocery)
        session.commit()

        deleted = session.get(PantryItem, pantry.id)
        assert deleted is None

    engine.dispose()
