#!/usr/bin/env python3
"""b4 — Smoke de bout en bout du miroir panier Intermarché.

Valide le flux complet du miroir panier en comparant à chaque étape l'état du
site (réponse de l'adapter) et l'état local du miroir (SupermarketCart réécrit
par `cart_mirror._commit_state`, exactement ce que font les endpoints).

Deux modes :

- ``--replay`` (offline, recommandé) : rejoue une séquence figée de réponses
  canned dérivées des fixtures ``tests/fixtures/intermarche/`` (elles-mêmes
  réduites de la HAR de session connectée) via ``httpx.MockTransport``. Aucun
  accès réseau. C'est le mode utilisé pour la validation b4 : la session
  cookies live (``data/cookies_intermarche.json``) répond 403 DataDome
  (session morte, cf. ``docs/agents/report-b-validation.md``), donc le flux
  live n'a pas pu être rejoué contre le vrai site — le replay offline contre
  les payloads réels capturés est accepté comme preuve suffisante.
- ``--cookies`` (live) : mode original, contre le vrai intermarche.com avec
  une session cookies connectée. À utiliser dès qu'une session fraîche est
  disponible pour ré-valider en conditions réelles.

Actions du flux (identiques dans les deux modes) :
  read  → GET  : re-lit le panier site → réécrit le local
  add   → POST : ajoute 1 article (depuis un cache row) → réécrit le local
  qty   → PATCH: modifie la quantité → réécrit le local
  rm    → DELETE item : supprime l'article → réécrit le local
  clear → DELETE cart : vide le panier site → vide le local

Usage:
  uv run python scripts/smoke_cart_mirror.py --replay
  uv run python scripts/smoke_cart_mirror.py --actions read,add,qty,rm \
      --cookies data/cookies_intermarche.json
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import SupermarketCart, SupermarketCartItem, SupermarketSearchCache, SupermarketStore
from app.services import cart_mirror
from app.services.scrapers.intermarche_cart import (
    IntermarcheCartClient,
    IntermarcheCartState,
    build_intermarche_cart_client,
)

STORE = SupermarketStore.INTERMARCHE
CUSTOMER_UUID = "515ffd9e-538e-447a-983e-69ca17363fac"  # récupéré dans le HAR connecté
STORE_ID = "11131"  # récupéré dans le HAR connecté (itm_pdv)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "intermarche"

# Un item présent dans le panier du HAR : Parmigiano reggiano, itemId 37731.
SMOKE_ITEM_ID = "37731"
SMOKE_ITEM_NAME = "Parmigiano reggiano AOP (smoke b4)"
SMOKE_ITEM_PRICE = 5.07

# Séquence figée pour le mode --replay : couvre le cycle complet demandé par
# b4 (ajout → vérif, quantité, suppression, re-ajout, vidage).
REPLAY_ACTIONS = ["read", "add", "qty", "rm", "add", "clear"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cookies", type=Path, help="session cookies live (mode réseau)")
    parser.add_argument("--replay", action="store_true", help="mode offline : rejoue des réponses canned")
    parser.add_argument("--customer-uuid", default=CUSTOMER_UUID)
    parser.add_argument(
        "--actions",
        default="",
        help="mode --cookies uniquement ; comma list: read,add,qty,rm,clear (défaut: probe read-only)",
    )
    parser.add_argument("--clear", action="store_true", help="mode --cookies uniquement ; autorise l'action clear (vide le vrai panier)")
    parser.add_argument("--db", type=Path, default=None, help="fichier sqlite (défaut: tmp)")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args()
    if not args.replay and not args.cookies:
        parser.error("un des deux modes est requis : --replay (offline) ou --cookies <fichier> (live)")
    if args.replay and args.cookies:
        parser.error("--replay et --cookies sont mutuellement exclusifs")
    return args


def _load_cookies(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("fichier cookies doit être une liste JSON")
    return payload


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _qty_bump_fixture() -> dict:
    """Synthétique : le fixture 1-item avec la quantité portée à 3.

    Aucun fixture disque ne capture ce cas (changement de quantité sur une
    ligne existante) ; on part du payload réel `cart_response_1_item.json` et
    on ne modifie que la quantité/le montant, en conservant la forme exacte
    (mêmes clés `item`) capturée dans la HAR.
    """
    payload = copy.deepcopy(_load_fixture("cart_response_1_item.json"))
    payload["carts"][0]["items"][0]["quantity"] = 3
    payload["carts"][0]["amount"] = round(SMOKE_ITEM_PRICE * 3, 2)
    payload["amount"] = round(SMOKE_ITEM_PRICE * 3, 2)
    return payload


def _replay_responses() -> list[httpx.Response]:
    """Réponses canned, une par étape de ``REPLAY_ACTIONS`` (dans l'ordre)."""
    fixtures = [
        _load_fixture("cart_response_empty.json"),  # read  : panier site vide
        _load_fixture("cart_response_1_item.json"),  # add   : +1 article (qty 1)
        _qty_bump_fixture(),  # qty   : quantité portée à 3
        _load_fixture("cart_response_empty.json"),  # rm    : article supprimé
        _load_fixture("cart_response_1_item.json"),  # add   : re-ajout (qty 1)
    ]
    responses = [
        httpx.Response(200, json=payload, headers={"content-type": "application/json"})
        for payload in fixtures
    ]
    responses.append(httpx.Response(204))  # clear : DELETE → 204
    return responses


def _build_replay_client(customer_uuid: str, store_id: str) -> IntermarcheCartClient:
    responses = iter(_replay_responses())

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return IntermarcheCartClient(http_client, customer_uuid=customer_uuid, store_id=store_id)


def _summary(state: IntermarcheCartState | None) -> dict:
    if state is None:
        return {"items": [], "items_number": 0, "amount": 0.0}
    return {
        "items": [
            {"id": i.item_id, "name": i.name, "quantity": i.quantity, "price": i.price}
            for i in state.items
        ],
        "items_number": state.items_number,
        "amount": state.amount,
    }


def _local_rows(session: Session, user_id: int) -> list[dict]:
    cart = session.exec(
        select(SupermarketCart).where(
            SupermarketCart.store == STORE, SupermarketCart.user_id == user_id
        )
    ).first()
    if cart is None:
        return []
    rows = session.exec(
        select(SupermarketCartItem).where(SupermarketCartItem.cart_id == cart.id)
    ).all()
    return [
        {"external_id": r.external_id, "name": r.name, "quantity": r.quantity}
        for r in rows
    ]


def _seed_cache(session: Session) -> int:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=STORE,
        query="parmigiano",
        external_id=SMOKE_ITEM_ID,
        name=SMOKE_ITEM_NAME,
        brand="Parmigiano Reggiano",
        packaging="150 g",
        price_amount=SMOKE_ITEM_PRICE,
        price_text="5,07 €",
        image_url="https://img.test/smoke.png",
        product_url="https://example.test/smoke",
        fetched_at=now,
        expires_at=now + timedelta(days=1),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.id


def _matches(site: dict, local: list[dict]) -> bool:
    site_items = {i["id"]: i["quantity"] for i in site.get("items", [])}
    local_items = {i["external_id"]: i["quantity"] for i in local if i["quantity"] > 0}
    return site_items == local_items


async def _run_action(name: str, client, site_id: str, session, user_id: int) -> dict:
    """Execute one mirror action through the adapter and record site+local."""
    if name == "read":
        state = await client.get_or_read_cart()
        cart_mirror._commit_state(session, user_id, state)
    elif name == "add":
        state = await client.add_item(site_id, quantity=1)
        cart_mirror._commit_state(session, user_id, state)
    elif name == "qty":
        # Même protocole que l'endpoint PATCH : read d'abord, puis delta.
        await client.get_or_read_cart()
        state = await client.update_item_quantity(site_id, 3)
        cart_mirror._commit_state(session, user_id, state)
    elif name == "rm":
        await client.get_or_read_cart()
        state = await client.remove_item(site_id)
        cart_mirror._commit_state(session, user_id, state)
    elif name == "clear":
        await client.clear_cart()
        cart_mirror._commit_state(session, user_id, None)
        state = None
    else:
        raise SystemExit(f"action inconnue: {name}")

    site = _summary(state) if state is not None else {"items": [], "items_number": 0, "amount": 0.0, "cleared_site": True}
    local = _local_rows(session, user_id)
    return {"action": name, "site": site, "local": local, "match": _matches(site, local)}


async def main() -> int:
    args = parse_args()

    if args.db is None:
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(tmp.name)
        tmp.close()
    else:
        db_path = args.db
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    # user_id utilisé : 1 (Owner), comme le chemin backend réel.
    user_id = 1

    if args.replay:
        mode = "replay (offline)"
        actions = list(REPLAY_ACTIONS)
        client = _build_replay_client(args.customer_uuid, STORE_ID)
    else:
        mode = "live"
        cookies = _load_cookies(args.cookies)
        actions = [a.strip() for a in args.actions.split(",") if a.strip()] if args.actions else []
        if "clear" in actions and not args.clear:
            raise SystemExit("refus: --clear nécessaire pour vider le vrai panier en mode live")
        client = build_intermarche_cart_client(cookies, customer_uuid=args.customer_uuid)

    results: list[dict] = []
    status = "pending"
    error = None
    try:
        with Session(engine) as session:
            if any(a in actions for a in ("add", "qty", "rm")):
                # seed un cache row pour le flux add (comme le ferait /search)
                _seed_cache(session)
            for action in actions:
                results.append(await _run_action(action, client, SMOKE_ITEM_ID, session, user_id))
            if not actions:
                # mode probe : unique read, read-only
                state = await client.get_or_read_cart()
                cart_mirror._commit_state(session, user_id, state)
                local = _local_rows(session, user_id)
                results.append(
                    {
                        "action": "read (probe)",
                        "site": _summary(state),
                        "local": local,
                        "match": _matches(_summary(state), local),
                    }
                )
            status = "ok"
    except Exception as exc:  # noqa: BLE001
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
    finally:
        await client.aclose()

    report = {
        "status": status,
        "mode": mode,
        "customer_uuid": args.customer_uuid,
        "run_at": datetime.now(UTC).isoformat(),
        "actions": results,
        "error": error,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"\n=== Smoke miroir panier Intermarché — mode: {mode} — statut: {status} ===")
        if error:
            print(f"ERREUR: {error}")
        for r in results:
            site = r["site"]
            local_ext = {i["external_id"]: i["quantity"] for i in r["local"]}
            site_ext = {i["id"]: i["quantity"] for i in site.get("items", [])}
            print(f"\n[{r['action']}] match={r['match']}")
            print(f"  site  : {json.dumps(site_ext, ensure_ascii=False)}")
            print(f"  local : {json.dumps(local_ext, ensure_ascii=False)}")
        print()
        print("Site vs local :", "OK" if results and all(r["match"] for r in results) else "DISCREPANCE")

    # Nettoyage
    try:
        engine.dispose()
    finally:
        if args.db is None and db_path.exists():
            db_path.unlink()

    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
