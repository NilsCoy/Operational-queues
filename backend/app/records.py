from __future__ import annotations

from datetime import date, timedelta

from .models import AppState, OperationRecord


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def week_end(value: date) -> date:
    return week_start(value) + timedelta(days=6)


def matches_query(record: OperationRecord, query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = f"{record.big_operations}\n{record.small_operations}".lower()
    return needle in haystack


def list_records(
    state: AppState, week_of: date | None = None, q: str | None = None
) -> list[OperationRecord]:
    records = list(state.records)
    if week_of is not None:
        start = week_start(week_of)
        records = [r for r in records if start <= r.day <= week_end(week_of)]
    if q and q.strip():
        records = [r for r in records if matches_query(r, q)]
    records.sort(key=lambda r: (r.day, r.id))
    return records


def add_record(
    state: AppState, day: date, big_operations: str = "", small_operations: str = ""
) -> OperationRecord:
    record = OperationRecord(
        id=state.next_record_id,
        day=day,
        big_operations=big_operations,
        small_operations=small_operations,
    )
    state.next_record_id += 1
    state.records.append(record)
    return record


def update_record(
    state: AppState,
    record_id: int,
    day: date | None = None,
    big_operations: str | None = None,
    small_operations: str | None = None,
) -> OperationRecord | None:
    for record in state.records:
        if record.id != record_id:
            continue
        if day is not None:
            record.day = day
        if big_operations is not None:
            record.big_operations = big_operations
        if small_operations is not None:
            record.small_operations = small_operations
        return record
    return None


def delete_record(state: AppState, record_id: int) -> bool:
    for index, record in enumerate(state.records):
        if record.id == record_id:
            del state.records[index]
            return True
    return False


def group_by_week(records: list[OperationRecord]) -> list[dict]:
    weeks: dict[date, list[OperationRecord]] = {}
    for record in records:
        weeks.setdefault(week_start(record.day), []).append(record)
    result = []
    for start in sorted(weeks):
        week_records = sorted(weeks[start], key=lambda r: (r.day, r.id))
        result.append(
            {
                "week_start": start.isoformat(),
                "week_end": week_end(start).isoformat(),
                "records": [r.model_dump(mode="json") for r in week_records],
            }
        )
    return result
