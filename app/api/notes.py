from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlmodel import select

from app.api._crud import apply_updates, create, delete, get_or_404, save
from app.api.deps import SessionDep, owner_only_user
from app.models import Note, NoteKind
from app.schemas import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(owner_only_user)])


@router.post("", response_model=NoteRead)
def create_note(payload: NoteCreate, session: SessionDep) -> NoteRead:
    note = create(session, Note(**payload.model_dump()))
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
    note = get_or_404(session, Note, note_id, detail="Note not found")
    return NoteRead.model_validate(note, from_attributes=True)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(note_id: int, payload: NoteUpdate, session: SessionDep) -> NoteRead:
    note = get_or_404(session, Note, note_id, detail="Note not found")

    updates = payload.model_dump(exclude_unset=True)
    apply_updates(note, updates, touch=True)
    note = save(session, note)
    return NoteRead.model_validate(note, from_attributes=True)


@router.delete("/{note_id}")
def delete_note(note_id: int, session: SessionDep) -> dict:
    note = get_or_404(session, Note, note_id, detail="Note not found")
    delete(session, note)
    return {"ok": True, "deleted_id": note_id}
