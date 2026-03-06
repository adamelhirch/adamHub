from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Note, NoteKind
from app.schemas import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=NoteRead)
def create_note(payload: NoteCreate, session: SessionDep) -> NoteRead:
    note = Note(**payload.model_dump())
    session.add(note)
    session.commit()
    session.refresh(note)
    return NoteRead.model_validate(note, from_attributes=True)


@router.get("", response_model=list[NoteRead])
def list_notes(
    session: SessionDep,
    kind: NoteKind | None = None,
    tag: str | None = None,
    q: str | None = None,
    pinned: bool | None = None,
    limit: int = Query(default=300, ge=1, le=1000),
) -> list[NoteRead]:
    statement = select(Note).order_by(Note.pinned.desc(), Note.updated_at.desc()).limit(limit)
    if kind:
        statement = statement.where(Note.kind == kind)
    if pinned is not None:
        statement = statement.where(Note.pinned == pinned)

    notes = session.exec(statement).all()

    if tag:
        notes = [note for note in notes if tag in note.tags]
    if q:
        ql = q.lower()
        notes = [note for note in notes if ql in note.title.lower() or ql in note.content.lower()]

    return [NoteRead.model_validate(note, from_attributes=True) for note in notes]


@router.get("/journal", response_model=list[NoteRead])
def list_journal_entries(
    session: SessionDep,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[NoteRead]:
    statement = select(Note).where(Note.kind == NoteKind.JOURNAL).order_by(Note.created_at.desc()).limit(limit)
    notes = session.exec(statement).all()

    if from_date:
        notes = [note for note in notes if note.created_at.date() >= from_date]
    if to_date:
        notes = [note for note in notes if note.created_at.date() <= to_date]

    return [NoteRead.model_validate(note, from_attributes=True) for note in notes]


@router.get("/{note_id}", response_model=NoteRead)
def get_note(note_id: int, session: SessionDep) -> NoteRead:
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteRead.model_validate(note, from_attributes=True)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(note_id: int, payload: NoteUpdate, session: SessionDep) -> NoteRead:
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(note, key, value)

    note.updated_at = datetime.now(timezone.utc)
    session.add(note)
    session.commit()
    session.refresh(note)
    return NoteRead.model_validate(note, from_attributes=True)


@router.delete("/{note_id}")
def delete_note(note_id: int, session: SessionDep) -> dict:
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    session.delete(note)
    session.commit()
    return {"ok": True, "deleted_id": note_id}
