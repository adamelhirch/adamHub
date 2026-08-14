from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import CalendarCategory, CalendarSource, EventType


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    location: str | None = None
    type: EventType = EventType.PERSONAL
    all_day: bool = False
    tags: list[str] = Field(default_factory=list)


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None
    type: EventType | None = None
    all_day: bool | None = None
    tags: list[str] | None = None


class EventRead(BaseModel):
    id: int
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    location: str | None
    type: EventType
    all_day: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CalendarItemCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    category: CalendarCategory = CalendarCategory.GENERAL
    notification_enabled: bool = True
    reminder_offsets_min: list[int] = Field(default_factory=lambda: [60])
    extra_data: dict = Field(default_factory=dict, validation_alias="metadata", serialization_alias="metadata")


class CalendarItemUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    category: CalendarCategory | None = None
    completed: bool | None = None
    notification_enabled: bool | None = None
    reminder_offsets_min: list[int] | None = None
    extra_data: dict | None = Field(default=None, validation_alias="metadata", serialization_alias="metadata")


class CalendarItemRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    all_day: bool
    category: CalendarCategory
    source: CalendarSource
    source_ref_id: int | None
    generated: bool
    completed: bool
    notification_enabled: bool
    reminder_offsets_min: list[int]
    extra_data: dict = Field(validation_alias="extra_data", serialization_alias="metadata")
    last_notified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalendarSyncResult(BaseModel):
    synced: int
    removed: int
    generated_by_source: dict[str, int]
    synced_at: datetime


class CalendarFeedCreate(BaseModel):
    name: str
    sources: list[CalendarSource] = Field(default_factory=list)
    include_completed: bool = True


class CalendarFeedRead(BaseModel):
    id: int
    name: str
    token: str
    sources: list[CalendarSource] = Field(default_factory=list)
    include_completed: bool
    active: bool
    ics_url: str
    webcal_url: str
    last_accessed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalendarReminderRead(BaseModel):
    item: CalendarItemRead
    due_at: datetime
    minutes_before: int
