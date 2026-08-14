from __future__ import annotations

import re


SCHEDULE_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


def _normalize_schedule_times(
    schedule_time: str | None,
    schedule_times: list[str] | None,
) -> tuple[str | None, list[str]]:
    pattern = re.compile(SCHEDULE_TIME_PATTERN)
    combined = [
        value
        for value in [schedule_time, *(schedule_times or [])]
        if value is not None and value != ""
    ]
    for value in combined:
        if pattern.fullmatch(value) is None:
            raise ValueError("schedule_times must use HH:MM format")
    unique_times = sorted(set(combined))
    return (unique_times[0] if unique_times else None, unique_times)


def _normalize_schedule_weekdays(
    schedule_weekday: int | None,
    schedule_weekdays: list[int] | None,
) -> tuple[int | None, list[int]]:
    combined = [
        value
        for value in [schedule_weekday, *(schedule_weekdays or [])]
        if value is not None
    ]
    for value in combined:
        if value < 0 or value > 6:
            raise ValueError("schedule_weekdays values must be between 0 and 6")
    unique_days = sorted(set(combined))
    return (unique_days[0] if unique_days else None, unique_days)
