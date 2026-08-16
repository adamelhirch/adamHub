"""Smoke test a3 — valide les 4 recherches (intermarche, carrefour, leclerc, auchan).

Exerce le chemin backend complet (``fetch_search_results`` avec la connexion
active en base : cookies déchiffrés + sélection magasin Auchan persistée),
comme le fait ``POST /supermarket/search``. Avec ``--cookies-fs``, appelle les
scrapers en direct avec les cookies du ``data/`` local (Intermarché/Carrefour/
Leclerc) et un contexte magasin Auchan par défaut. Rapport par enseigne : nb
résultats, latence, erreur éventuelle.

Usage:
    uv run python scripts/smoke_search_all.py [--query lait] [--max-results 10]
    uv run python scripts/smoke_search_all.py --cookies-fs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from sqlmodel import Session, create_engine  # noqa: E402

from app.models import SupermarketStore  # noqa: E402
from app.services.store_catalog import fetch_search_results  # noqa: E402

# Contexte magasin Auchan par défaut (référence live : Toulouse Pontjumeaux),
# utilisé uniquement en mode --cookies-fs (le mode backend lit la sélection DB).
from app.services.scrapers.auchan import (  # noqa: E402
    AuchanStoreContext,
    search_auchan,
)
from app.services.scrapers.carrefour import search_carrefour  # noqa: E402
from app.services.scrapers.intermarche import search_intermarche  # noqa: E402
from app.services.scrapers.leclerc import search_leclerc  # noqa: E402

DEFAULT_AUCHAN_STORE = AuchanStoreContext(
    seller_id="4c663296-54a8-45f6-b385-0be86b4dfe98",
    store_reference="6007",
    channel="PICK_UP",
    zipcode="31400",
    city="Toulouse",
    country="France",
    latitude=43.604464,
    longitude=1.444243,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="lait")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument(
        "--cookies-fs",
        action="store_true",
        help="Scrapers en direct avec les cookies du data/ (pas de base de données).",
    )
    parser.add_argument("--user-id", type=int, default=1, help="User dont la connexion active est lue (mode backend).")
    return parser.parse_args()


def _summary(report: dict) -> str:
    err = report["erreur"] or "-"
    sample = report.get("exemple") or {}
    label = sample.get("name", "-")
    return (
        f"[{report['enseigne']:12}] nb={report['nb_resultats']:3} "
        f"lat={report['latence_s']:6.2f}s err={err[:60]} ex={label[:45]}"
    )


async def _backend(store: SupermarketStore, query: str, max_results: int, user_id: int) -> dict:
    db_url = os.environ.get("ADAMHUB_DB_URL")
    if not db_url:
        raise RuntimeError("ADAMHUB_DB_URL absente — chargez le .env local.")
    engine = create_engine(db_url)
    with Session(engine) as session:
        rows = await fetch_search_results(
            store=store,
            queries=[query],
            max_results=max_results,
            session=session,
            user_id=user_id,
        )
    return rows


async def _direct(store: SupermarketStore, query: str, max_results: int) -> list:
    if store == SupermarketStore.INTERMARCHE:
        res = await search_intermarche(queries=[query], max_results=max_results)
    elif store == SupermarketStore.CARREFOUR:
        res = await search_carrefour(queries=[query], max_results=max_results)
    elif store == SupermarketStore.LECLERC:
        res = await search_leclerc(queries=[query], max_results=max_results)
    elif store == SupermarketStore.AUCHAN:
        res = await search_auchan(
            queries=[query],
            max_results=max_results,
            store_selection=DEFAULT_AUCHAN_STORE,
        )
    else:
        raise ValueError(f"Unsupported store: {store}")
    return [item for items in res.values() for item in items]


async def run_store(
    store: SupermarketStore,
    query: str,
    max_results: int,
    cookies_fs: bool,
    user_id: int,
) -> dict:
    t0 = time.monotonic()
    try:
        rows = (
            await _direct(store, query, max_results)
            if cookies_fs
            else await _backend(store, query, max_results, user_id)
        )
        elapsed = time.monotonic() - t0
        first = rows[0] if rows else {}
        return {
            "enseigne": store.value,
            "nb_resultats": len(rows),
            "latence_s": round(elapsed, 2),
            "erreur": None,
            "exemple": {
                "name": first.get("name"),
                "price": first.get("price_text") or first.get("price"),
                "id": first.get("external_id") or first.get("id"),
            },
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - t0
        return {
            "enseigne": store.value,
            "nb_resultats": 0,
            "latence_s": round(elapsed, 2),
            "erreur": f"{type(exc).__name__}: {exc}",
            "exemple": None,
        }


async def main() -> int:
    args = parse_args()
    stores = [
        SupermarketStore.INTERMARCHE,
        SupermarketStore.CARREFOUR,
        SupermarketStore.LECLERC,
        SupermarketStore.AUCHAN,
    ]
    mode = "cookies-fs (direct)" if args.cookies_fs else f"backend (DB, user_id={args.user_id})"
    print(f"=== Smoke a3 — {mode} — query={args.query!r} max={args.max_results} ===")
    reports = [
        await run_store(store, args.query, args.max_results, args.cookies_fs, args.user_id)
        for store in stores
    ]
    for report in reports:
        print(_summary(report))
    print("\n" + json.dumps(reports, ensure_ascii=False, indent=2))

    failed = [r for r in reports if r["erreur"] is not None or r["nb_resultats"] == 0]
    print(f"\nRÉSULTAT GLOBAL: {'OK (4/4)' if not failed else f'PARTIEL — {len(failed)}/4 en erreur'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
