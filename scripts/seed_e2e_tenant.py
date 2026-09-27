"""Seed and reset isolated tenant data for Playwright E2E tests."""
from __future__ import annotations

import sys
from sqlmodel import Session, select
from app.core.db import engine
from app.core.auth import hash_password
from app.models import (
    User,
    Recipe,
    RecipeIngredient,
    GroceryItem,
    PantryItem,
    GroceryToCartJob,
    MatchedCartItem,
)

E2E_EMAIL = "e2e-tester@adamelhirch.com"
E2E_PASSWORD = "TestPassword123!"
E2E_NAME = "E2E Tester"

def seed_e2e_tenant(reset_data: bool = True) -> int:
    with Session(engine) as session:
        # 1. Ensure user exists
        user = session.exec(select(User).where(User.email == E2E_EMAIL)).first()
        if not user:
            user = User(
                email=E2E_EMAIL,
                password_hash=hash_password(E2E_PASSWORD),
                display_name=E2E_NAME,
                email_verified=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"[seed] Created user {user.id} ({user.email})")
        else:
            user.email_verified = True
            session.add(user)
            session.commit()
            print(f"[seed] Found user {user.id} ({user.email})")

        uid = user.id

        if reset_data:
            # Clean up user's old jobs & matched items
            jobs = session.exec(select(GroceryToCartJob).where(GroceryToCartJob.user_id == uid)).all()
            for j in jobs:
                matched = session.exec(select(MatchedCartItem).where(MatchedCartItem.job_id == j.id)).all()
                for m in matched:
                    session.delete(m)
                session.delete(j)

            # Clean up user's groceries
            groceries = session.exec(select(GroceryItem).where(GroceryItem.user_id == uid)).all()
            for g in groceries:
                session.delete(g)

            # Clean up user's pantry
            pantry = session.exec(select(PantryItem).where(PantryItem.user_id == uid)).all()
            for p in pantry:
                session.delete(p)

            session.commit()
            print(f"[seed] Reset groceries, pantry, and cart jobs for user {uid}")

        # Ensure canonical benchmark recipes exist for this user
        existing_recipes = {r.name: r for r in session.exec(select(Recipe).where(Recipe.user_id == uid)).all()}

        # Source recipes from user 1
        source_recipes = session.exec(select(Recipe).where(Recipe.user_id == 1)).all()
        for src in source_recipes:
            if src.name not in existing_recipes:
                cloned = Recipe(
                    user_id=uid,
                    name=src.name,
                    description=src.description,
                    instructions=src.instructions,
                    steps=src.steps,
                    utensils=src.utensils,
                    prep_minutes=src.prep_minutes,
                    cook_minutes=src.cook_minutes,
                    servings=src.servings,
                    tags=src.tags,
                )
                session.add(cloned)
                session.commit()
                session.refresh(cloned)

                # Clone ingredients
                src_ings = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == src.id)).all()
                for ing in src_ings:
                    cloned_ing = RecipeIngredient(
                        recipe_id=cloned.id,
                        name=ing.name,
                        quantity=ing.quantity,
                        unit=ing.unit,
                        note=ing.note,
                        category=ing.category,
                        cache_id=ing.cache_id,
                        store=ing.store,
                        store_label=ing.store_label,
                        external_id=ing.external_id,
                        packaging=ing.packaging,
                        price_text=ing.price_text,
                        product_url=ing.product_url,
                        image_url=ing.image_url,
                    )
                    session.add(cloned_ing)
                session.commit()
                print(f"[seed] Cloned recipe '{cloned.name}' with {len(src_ings)} ingredients to user {uid}")

    return uid

if __name__ == "__main__":
    reset = "--no-reset" not in sys.argv
    seed_e2e_tenant(reset_data=reset)
