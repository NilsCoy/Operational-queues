from __future__ import annotations

from datetime import date, timedelta

from .models import AppState, OperationRecord


def week_start(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def week_end(day: date) -> date:
    return week_start(day) + timedelta(days=6)


def list_records(state: AppState, week_of: date | None) -> list[OperationRecord]:
    records = state.records
    if week_of is not None:
        start, end = week_start(week_of), week_end(week_of)
        records = [r for r in records if start <= r.day <= end]
    return sorted(records, key=lambda r: (r.day, r.id))


def add_record(state: AppState, day: date, big: str, small: str) -> OperationRecord:
    record = OperationRecord(
        id=state.next_record_id,
        day=day,
        big_operations=big,
        small_operations=small,
    )
    state.next_record_id += 1
    state.records.append(record)
    return record


def update_record(
    state: AppState, record_id: int, day: date | None, big: str | None, small: str | None
) -> OperationRecord | None:
    for record in state.records:
        if record.id == record_id:
            if day is not None:
                record.day = day
            if big is not None:
                record.big_operations = big
            if small is not None:
                record.small_operations = small
            return record
    return None


def delete_record(state: AppState, record_id: int) -> bool:
    before = len(state.records)
    state.records = [r for r in state.records if r.id != record_id]
    return len(state.records) < before


def group_by_week(records: list[OperationRecord]) -> list[dict]:
    """Group records into weeks (Monday-based), newest week first."""
    weeks: dict[date, list[OperationRecord]] = {}
    for record in records:
        weeks.setdefault(week_start(record.day), []).append(record)
    grouped = []
    for start in sorted(weeks, reverse=True):
        rows = sorted(weeks[start], key=lambda r: (r.day, r.id))
        grouped.append(
            {
                "week_start": start.isoformat(),
                "week_end": (start + timedelta(days=6)).isoformat(),
                "records": [r.model_dump(mode="json") for r in rows],
            }
        )
    return grouped