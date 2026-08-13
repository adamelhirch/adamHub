#!/usr/bin/env python3
"""One-off operational backfill: assign legacy NULL-user rows to the owner tenant.

After the additive multi-tenant migration (user_id on groceryitem/pantryitem/
recipe/mealplan), pre-existing rows have user_id = NULL and are invisible to
everyone. This script claims them for the account whose email is given with
--email (which must already exist — register it first via POST /auth/register).

Default is a dry run that only prints how many NULL rows exist per table.
Pass --commit to actually set user_id on those rows inside a transaction.
Safe to re-run: after a commit, a fresh dry run reports 0 remaining NULL rows.

Usage:
    python scripts/backfill_owner_tenant.py --email you@example.com
    python scripts/backfill_owner_tenant.py --email you@example.com --commit
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from sqlmodel import Session, func, select, update

from app.core.config import get_settings  # noqa: F401  (loads .env)
from app.core.db import engine
from app.models import GroceryItem, MealPlan, PantryItem, Recipe, User

BACKFILL_MODELS = [GroceryItem, PantryItem, Recipe, MealPlan]


def count_null_rows(session: Session) -> dict[str, int]:
    """Count rows per table whose user_id is NULL."""
    counts: dict[str, int] = {}
    for model in BACKFILL_MODELS:
        total = session.exec(
            select(func.count())
            .select_from(model)
            .where(model.user_id.is_(None))
        ).one()
        counts[model.__tablename__] = int(total or 0)
    return counts


def resolve_owner(session: Session, email: str) -> User | None:
    """Look up an EXISTING user by email. Never creates one."""
    return session.exec(
        select(User).where(User.email == (email or "").strip().lower())
    ).first()


def backfill(session: Session, user_id: int, *, commit: bool) -> dict:
    """Count (and, when commit=True, claim) NULL-user rows for the given user.

    Returns {"counts": {...}, "updated": {...}, "commit": bool}. When commit is
    False, `updated` is all zeros. When commit is True the update runs inside the
    caller-provided session and is committed here.
    """
    counts = count_null_rows(session)
    updated: dict[str, int] = {name: 0 for name in counts}

    if commit:
        for model in BACKFILL_MODELS:
            result = session.exec(
                update(model)
                .where(model.user_id.is_(None))
                .values(user_id=user_id)
            )
            updated[model.__tablename__] = int(result.rowcount or 0)
        session.commit()

    return {"counts": counts, "updated": updated, "commit": commit}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of the EXISTING user to claim NULL rows for")
    parser.add_argument("--commit", action="store_true", help="Actually write user_id; default is a dry run")
    args = parser.parse_args(argv)

    with Session(engine) as session:
        user = resolve_owner(session, args.email)
        if user is None:
            print(
                f"ERROR: no user with email '{args.email}' exists. "
                "Register that account first via POST /auth/register.",
                file=sys.stderr,
            )
            return 1

        result = backfill(session, user.id, commit=args.commit)

        print(f"Owner tenant: {user.email} (id={user.id})")
        for name in BACKFILL_MODELS:
            table = name.__tablename__
            counts = result["counts"][table]
            updated = result["updated"][table]
            if result["commit"]:
                print(f"  {table:14} {counts} NULL rows -> {updated} assigned")
            else:
                print(f"  {table:14} {counts} NULL rows (dry run, pass --commit to assign)")
        if result["commit"]:
            remaining = sum(result["counts"].values()) - sum(result["updated"].values())
            print(f"Done. Remaining NULL rows: {remaining}")
        else:
            print("Dry run only. Re-run with --commit to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
