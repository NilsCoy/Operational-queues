from __future__ import annotations

from datetime import date, timedelta

from .models import OperationRecord


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def week_end(value: date) -> date:
    return week_start(value) + timedelta(days=6)


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
