"""CLI script to seed canonical Merise models in AdamHUB."""
from __future__ import annotations

import sys
from sqlmodel import Session

from app.core.db import engine
from app.services.canonical_seed import seed_canonical_data


def main() -> None:
    print("[seed] Seeding canonical Merise reference data...")
    with Session(engine) as session:
        counts = seed_canonical_data(session)
    print(f"[seed] Done: {counts}")


if __name__ == "__main__":
    main()
