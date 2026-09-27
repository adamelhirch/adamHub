from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models import (
    GroceryItem,
    GroceryToCartJob,
    MatchedCartItem,
    SubstituteProposal,
    SupermarketSearchCache,
    SupermarketStore,
    UserStorePreference,
)
from app.schemas.supermarket import (
    ConfirmPickupResponse,
    CreateCartJobPayload,
    GroceryToCartJobRead,
    MatchedCartItemRead,
    RefineJobPayload,
    SubstituteProposalRead,
    SyncJobResponse,
    UpdateMatchedItemPayload,
)
import asyncio
import re
from app.services.grocery_pantry import sync_checked_grocery_item_to_pantry
from app.services.supermarket.cart_matcher import CartMatcherService, extract_ingredient_keywords
from app.services.supermarket.store_locator import SupermarketStoreLocator


class CartJobService:
    """Orchestrates local staging of drive carts from grocery lists."""

    @classmethod
    async def enrich_cache_for_items(
        cls,
        session: Session,
        user_id: int,
        store: SupermarketStore,
        item_ids: list[int] | None = None,
    ) -> None:
        """Pre-fetch and cache real supermarket catalog items for uncached grocery items."""
        stmt = select(GroceryItem).where(
            GroceryItem.user_id == user_id,
            GroceryItem.checked == False,
        )
        if item_ids:
            stmt = stmt.where(col(GroceryItem.id).in_(item_ids))
        items = list(session.exec(stmt).all())

        missing_queries: list[str] = []
        for it in items:
            # Check if there is already a valid product match in this store's cache
            matched = CartMatcherService.match_grocery_item(
                session,
                it,
                store=store,
                strategy="mdd",
                user_id=user_id,
            )
            if matched is not None and matched.match_type != "substitute":
                continue

            clean_q = re.sub(r"\(.*?\)", "", it.name).strip()
            if not clean_q or len(clean_q) < 2:
                continue

            clean_lower = clean_q.lower()
            if clean_lower == "sel":
                search_q = "sel fin"
            elif clean_lower == "ail":
                search_q = "ail"
            else:
                search_q = clean_q

            if search_q not in missing_queries:
                missing_queries.append(search_q)

        if not missing_queries:
            return

        try:
            async with asyncio.timeout(7.0):
                from app.services.store_catalog import fetch_search_results, upsert_search_cache
                normalized = await fetch_search_results(
                    store=store,
                    queries=missing_queries[:8],
                    max_results=3,
                    session=session,
                    user_id=user_id,
                )
                if normalized:
                    upsert_search_cache(session, store, normalized)
                    session.commit()
        except Exception:
            pass

    @classmethod
    def create_draft_job(
        cls,
        session: Session,
        user_id: int,
        payload: CreateCartJobPayload,
    ) -> GroceryToCartJob:
        """Create a local staging draft cart job without mutating remote carts."""
        # 1. Resolve store external id and strategy
        store = payload.store
        strategy = payload.optimization_strategy or "mdd"
        external_store_id = payload.external_store_id

        if not external_store_id:
            pref = SupermarketStoreLocator.get_user_preference(session, user_id, store)
            if pref:
                external_store_id = pref.external_store_id
                if not payload.optimization_strategy:
                    strategy = pref.optimization_strategy
            else:
                external_store_id = f"{store.value}_drive_default"

        # 2. Query target grocery items
        stmt = select(GroceryItem).where(
            GroceryItem.user_id == user_id,
            GroceryItem.checked == False,
        )
        if payload.item_ids:
            stmt = stmt.where(col(GroceryItem.id).in_(payload.item_ids))

        grocery_items = list(session.exec(stmt).all())

        now = datetime.now(UTC)
        job = GroceryToCartJob(
            user_id=user_id,
            store=store,
            external_store_id=external_store_id,
            status="reviewing",
            optimization_strategy=strategy,
            items_count=len(grocery_items),
            matched_count=0,
            substitutes_count=0,
            unmatched_count=0,
            estimated_total_cents=0,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        matched_items: list[MatchedCartItem] = []
        total_cents = 0
        matched_count = 0
        unmatched_count = 0
        substitutes_count = 0
        for item in grocery_items:
            matched = CartMatcherService.match_grocery_item(
                session,
                item,
                store=store,
                strategy=strategy,
                user_id=user_id,
            )
            if matched:
                matched.job_id = job.id
                session.add(matched)
                session.flush()
                matched_items.append(matched)
                matched_count += 1
                total_cents += matched.total_price_cents

                sub_proposal = CartMatcherService.find_substitute_proposal(
                    session,
                    item,
                    matched,
                    store=store,
                    strategy=strategy,
                )
                if sub_proposal:
                    sub_proposal.matched_item_id = matched.id
                    session.add(sub_proposal)
                    substitutes_count += 1
            else:
                unmatched_count += 1

        job.matched_count = matched_count
        job.substitutes_count = substitutes_count
        job.unmatched_count = unmatched_count
        job.estimated_total_cents = total_cents
        job.updated_at = datetime.now(UTC)
        session.add(job)
        session.commit()
        session.refresh(job)

        return job

    @classmethod
    def get_job(cls, session: Session, user_id: int, job_id: int) -> GroceryToCartJob | None:
        """Fetch a specific cart job belonging to the tenant."""
        stmt = select(GroceryToCartJob).where(
            GroceryToCartJob.id == job_id,
            GroceryToCartJob.user_id == user_id,
        )
        return session.exec(stmt).first()

    @classmethod
    def get_active_job(cls, session: Session, user_id: int) -> GroceryToCartJob | None:
        """Fetch the latest active cart job for the user (in reviewing or synced state)."""
        stmt = (
            select(GroceryToCartJob)
            .where(
                GroceryToCartJob.user_id == user_id,
                col(GroceryToCartJob.status).in_(["reviewing", "synced"]),
            )
            .order_by(col(GroceryToCartJob.updated_at).desc(), col(GroceryToCartJob.id).desc())
        )
        return session.exec(stmt).first()

    @classmethod
    def delete_job(cls, session: Session, user_id: int, job_id: int) -> None:
        """Delete a cart job, clean up items and revert associated grocery items in_cart status."""
        job = cls.get_job(session, user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Panier drive introuvable.")

        items = cls.get_job_items(session, job.id)
        for it in items:
            if it.grocery_item_id:
                g_item = session.get(GroceryItem, it.grocery_item_id)
                if g_item and g_item.user_id == user_id:
                    g_item.in_cart = False
                    session.add(g_item)

            subs = list(
                session.exec(
                    select(SubstituteProposal).where(
                        SubstituteProposal.matched_item_id == it.id
                    )
                ).all()
            )
            for s in subs:
                session.delete(s)

            session.delete(it)

        session.delete(job)
        session.commit()

    @classmethod
    def get_job_items(cls, session: Session, job_id: int) -> list[MatchedCartItem]:
        """Fetch all matched cart items for a job."""
        stmt = select(MatchedCartItem).where(MatchedCartItem.job_id == job_id)
        return list(session.exec(stmt).all())

    @classmethod
    def get_substitute_for_item(
        cls, session: Session, matched_item_id: int
    ) -> SubstituteProposal | None:
        stmt = select(SubstituteProposal).where(
            SubstituteProposal.matched_item_id == matched_item_id,
            SubstituteProposal.status == "pending",
        )
        return session.exec(stmt).first()

    @classmethod
    def job_to_read_dto(cls, session: Session, job: GroceryToCartJob) -> GroceryToCartJobRead:
        """Convert a job entity and its items into the read DTO."""
        items = cls.get_job_items(session, job.id)
        items_read: list[MatchedCartItemRead] = []

        for it in items:
            sub = cls.get_substitute_for_item(session, it.id)
            sub_dto = None
            if sub:
                sub_dto = SubstituteProposalRead(
                    id=sub.id,
                    alternative_cache_id=sub.alternative_cache_id,
                    alternative_name=sub.alternative_name,
                    alternative_brand=sub.alternative_brand,
                    alternative_unit_price_cents=sub.alternative_unit_price_cents,
                    price_difference_cents=sub.price_difference_cents,
                    reason=sub.reason,
                    status=sub.status,
                )

            items_read.append(
                MatchedCartItemRead(
                    id=it.id,
                    grocery_item_id=it.grocery_item_id,
                    cache_id=it.cache_id,
                    external_id=it.external_id,
                    name=it.name,
                    brand=it.brand,
                    packaging=it.packaging,
                    image_url=it.image_url,
                    product_url=it.product_url,
                    quantity=it.quantity,
                    unit_price_cents=it.unit_price_cents,
                    total_price_cents=it.total_price_cents,
                    match_type=it.match_type,
                    status=it.status,
                    custom_note=it.custom_note,
                    substitute_proposal=sub_dto,
                )
            )

        return GroceryToCartJobRead(
            id=job.id,
            store=job.store,
            external_store_id=job.external_store_id,
            status=job.status,
            optimization_strategy=job.optimization_strategy,
            items_count=job.items_count,
            matched_count=job.matched_count,
            substitutes_count=job.substitutes_count,
            unmatched_count=job.unmatched_count,
            estimated_total_cents=job.estimated_total_cents,
            error_message=job.error_message,
            synced_at=job.synced_at,
            completed_at=job.completed_at,
            items=items_read,
        )

    @classmethod
    def _recalculate_job_totals(cls, session: Session, job: GroceryToCartJob) -> None:
        items = cls.get_job_items(session, job.id)
        active_items = [it for it in items if it.status != "removed"]
        job.estimated_total_cents = sum(it.total_price_cents for it in active_items)
        job.matched_count = len([it for it in active_items if it.cache_id is not None])
        job.updated_at = datetime.now(UTC)
        session.add(job)
        session.commit()
        session.refresh(job)

    @classmethod
    def update_item(
        cls,
        session: Session,
        user_id: int,
        job_id: int,
        item_id: int,
        payload: UpdateMatchedItemPayload,
    ) -> MatchedCartItem:
        job = cls.get_job(session, user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Panier drive introuvable.")

        stmt = select(MatchedCartItem).where(
            MatchedCartItem.id == item_id,
            MatchedCartItem.job_id == job_id,
        )
        item = session.exec(stmt).first()
        if not item:
            raise HTTPException(status_code=404, detail="Article introuvable dans ce panier.")

        if payload.status is not None:
            item.status = payload.status
        if payload.custom_note is not None:
            item.custom_note = payload.custom_note
        if payload.quantity is not None:
            item.quantity = max(0.0, float(payload.quantity))
            item.total_price_cents = int(round(item.unit_price_cents * item.quantity))

        session.add(item)
        session.commit()
        session.refresh(item)

        cls._recalculate_job_totals(session, job)
        return item

    @classmethod
    def refine_job(
        cls,
        session: Session,
        user_id: int,
        job_id: int,
        payload: RefineJobPayload | None = None,
    ) -> GroceryToCartJob:
        job = cls.get_job(session, user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Panier drive introuvable.")

        # Apply adjustments if provided
        if payload and payload.adjustments:
            for adj in payload.adjustments:
                stmt = select(MatchedCartItem).where(
                    MatchedCartItem.id == adj.matched_item_id,
                    MatchedCartItem.job_id == job_id,
                )
                item = session.exec(stmt).first()
                if not item:
                    continue
                if adj.action == "remove":
                    item.status = "removed"
                elif adj.action == "accept_substitute" and adj.substitute_id:
                    sub = session.get(SubstituteProposal, adj.substitute_id)
                    if sub and sub.matched_item_id == item.id:
                        cache_row = session.get(SupermarketSearchCache, sub.alternative_cache_id)
                        if cache_row:
                            item.cache_id = cache_row.id
                            item.external_id = cache_row.external_id
                            item.name = cache_row.name
                            item.brand = cache_row.brand
                            item.packaging = cache_row.packaging
                            item.image_url = cache_row.image_url
                            item.product_url = cache_row.product_url
                            item.unit_price_cents = sub.alternative_unit_price_cents
                            item.total_price_cents = int(round(item.unit_price_cents * item.quantity))
                            item.match_type = "substitute"
                            item.status = "staged"
                            sub.status = "accepted"
                            session.add(sub)
                elif adj.action == "modify_with_note":
                    item.status = "to_modify"
                    if adj.custom_note:
                        item.custom_note = adj.custom_note
                session.add(item)
            session.commit()

        # Process any items in status "to_modify"
        items = cls.get_job_items(session, job.id)
        for it in items:
            if it.status == "to_modify":
                # Check for substitute proposal first
                sub = cls.get_substitute_for_item(session, it.id)
                if sub and not it.custom_note:
                    cache_row = session.get(SupermarketSearchCache, sub.alternative_cache_id)
                    if cache_row:
                        it.cache_id = cache_row.id
                        it.external_id = cache_row.external_id
                        it.name = cache_row.name
                        it.brand = cache_row.brand
                        it.packaging = cache_row.packaging
                        it.image_url = cache_row.image_url
                        it.product_url = cache_row.product_url
                        it.unit_price_cents = sub.alternative_unit_price_cents
                        it.total_price_cents = int(round(it.unit_price_cents * it.quantity))
                        it.match_type = "substitute"
                        it.status = "staged"
                        sub.status = "accepted"
                        session.add(sub)
                        session.add(it)
                        continue

                # If custom_note is present, search cache for the best matching product
                query_tokens = []
                if it.custom_note:
                    query_tokens.extend(it.custom_note.lower().split())
                if it.name:
                    query_tokens.extend(it.name.lower().split()[:2])

                cache_candidates = list(session.exec(
                    select(SupermarketSearchCache).where(
                        SupermarketSearchCache.store == job.store,
                        SupermarketSearchCache.price_amount > 0,
                    )
                ).all())

                best_cache = None
                best_score = -1
                for cand in cache_candidates:
                    score = 0
                    cand_name = (cand.name or "").lower()
                    for token in query_tokens:
                        if len(token) > 2 and token in cand_name:
                            score += 10
                    if "bio" in query_tokens and cand.brand and "bio" in cand.brand.lower():
                        score += 5
                    if score > best_score and score > 0:
                        best_score = score
                        best_cache = cand

                if best_cache:
                    it.cache_id = best_cache.id
                    it.external_id = best_cache.external_id
                    it.name = best_cache.name
                    it.brand = best_cache.brand
                    it.packaging = best_cache.packaging
                    it.image_url = best_cache.image_url
                    it.product_url = best_cache.product_url
                    it.unit_price_cents = int(round((best_cache.price_amount or 0.0) * 100))
                    it.total_price_cents = int(round(it.unit_price_cents * it.quantity))
                    it.match_type = "substitute"
                    it.status = "staged"
                    session.add(it)
                else:
                    it.status = "staged"
                    session.add(it)

        session.commit()
        cls._recalculate_job_totals(session, job)
        job.status = "reviewing"
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    @classmethod
    def sync_remote_cart(cls, session: Session, user_id: int, job_id: int) -> SyncJobResponse:
        job = cls.get_job(session, user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Panier drive introuvable.")

        items = cls.get_job_items(session, job.id)
        active_items = [it for it in items if it.status != "removed"]

        for it in active_items:
            it.status = "synced"
            session.add(it)
            if it.grocery_item_id:
                g_item = session.get(GroceryItem, it.grocery_item_id)
                if g_item and g_item.user_id == user_id:
                    # Constitution Principle III: in_cart = True, checked remains False
                    g_item.in_cart = True
                    g_item.checked = False
                    session.add(g_item)

        now = datetime.now(UTC)
        job.status = "synced"
        job.synced_at = now
        job.updated_at = now
        session.add(job)
        session.commit()
        session.refresh(job)

        return SyncJobResponse(
            id=job.id,
            status=job.status,
            synced_at=now,
            remote_cart_ref=f"{job.store.value}-cart-{job.id}",
            items_synced_count=len(active_items),
            message=f"{len(active_items)} articles synchronisés dans votre panier {job.store.value.capitalize()}.",
        )

    @classmethod
    def confirm_pickup(cls, session: Session, user_id: int, job_id: int) -> ConfirmPickupResponse:
        job = cls.get_job(session, user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Panier drive introuvable.")

        items = cls.get_job_items(session, job.id)
        active_items = [it for it in items if it.status != "removed"]
        restocked_count = 0

        for it in active_items:
            if it.grocery_item_id:
                g_item = session.get(GroceryItem, it.grocery_item_id)
                if g_item and g_item.user_id == user_id:
                    # Constitution Principle III: checked = True, triggers pantry sync
                    g_item.checked = True
                    g_item.in_cart = False
                    session.add(g_item)
                    session.commit()
                    session.refresh(g_item)
                    sync_res = sync_checked_grocery_item_to_pantry(session, g_item, user_id=user_id)
                    if sync_res.get("synced"):
                        restocked_count += 1

        now = datetime.now(UTC)
        job.status = "completed"
        job.completed_at = now
        job.updated_at = now
        session.add(job)
        session.commit()
        session.refresh(job)

        return ConfirmPickupResponse(
            id=job.id,
            status=job.status,
            completed_at=now,
            restocked_items_count=restocked_count,
            message=f"Retrait confirmé : {restocked_count} articles réapprovisionnés dans votre garde-manger.",
        )
