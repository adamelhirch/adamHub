from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.models import UbereatsAddress
from app.services.scrapers.ubereats import set_delivery_location


def list_addresses(session: Session) -> list[UbereatsAddress]:
    statement = select(UbereatsAddress).order_by(
        UbereatsAddress.is_active.desc(), UbereatsAddress.updated_at.desc()
    )
    return list(session.exec(statement).all())


def get_address(session: Session, address_id: int) -> UbereatsAddress | None:
    return session.get(UbereatsAddress, address_id)


def get_active_address(session: Session) -> UbereatsAddress | None:
    statement = select(UbereatsAddress).where(UbereatsAddress.is_active.is_(True)).limit(1)
    return session.exec(statement).first()


def create_address(
    session: Session,
    *,
    label: str,
    formatted_address: str,
    latitude: float,
    longitude: float,
    subtitle: str | None = None,
    reference: str | None = None,
    reference_type: str = "GOOGLE_PLACES",
) -> UbereatsAddress:
    now = datetime.now(UTC)
    address = UbereatsAddress(
        label=label.strip() or formatted_address[:60],
        formatted_address=formatted_address.strip(),
        subtitle=subtitle,
        latitude=latitude,
        longitude=longitude,
        reference=reference,
        reference_type=reference_type or "GOOGLE_PLACES",
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


def delete_address(session: Session, address_id: int) -> UbereatsAddress | None:
    address = get_address(session, address_id)
    if address is None:
        return None
    session.delete(address)
    session.commit()
    return address


async def activate_address(session: Session, address_id: int) -> UbereatsAddress | None:
    address = get_address(session, address_id)
    if address is None:
        return None

    now = datetime.now(UTC)
    for other in list_addresses(session):
        if other.is_active and other.id != address.id:
            other.is_active = False
            other.updated_at = now
            session.add(other)
    address.is_active = True
    address.updated_at = now
    session.add(address)
    session.commit()
    session.refresh(address)

    payload: dict[str, Any] = {
        "address": {
            "title": address.label,
            "subtitle": address.subtitle or "",
            "eaterFormattedAddress": address.formatted_address,
            "address1": address.formatted_address,
        },
        "latitude": address.latitude,
        "longitude": address.longitude,
        "reference": address.reference or "",
        "referenceType": address.reference_type or "GOOGLE_PLACES",
    }
    await set_delivery_location(payload)

    return address
