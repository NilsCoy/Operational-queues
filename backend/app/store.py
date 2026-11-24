from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from . import db
from .models import OperationRecord, PinCode

# Roles renamed between versions: legacy value -> current value.
LEGACY_ROLE_MAP = {"user": "reader"}


class _LegacyState(BaseModel):
    records: list[OperationRecord] = Field(default_factory=list)
    pins: list[PinCode] = Field(default_factory=list)


def _map_legacy_roles(raw: dict) -> dict:
    for pin in raw.get("pins", []) or []:
        if isinstance(pin, dict) and pin.get("role") in LEGACY_ROLE_MAP:
            pin["role"] = LEGACY_ROLE_MAP[pin["role"]]
    return raw


def migrate_from_json(conn: sqlite3.Connection, json_path: Path) -> bool:
    """One-time import of the legacy data/state.json into SQLite.

    The JSON file is renamed to state.json.migrated-<ts> afterwards, so the
    import never runs twice. Returns True when data was actually imported.
    """
    if not json_path.exists():
        return False
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        state = _LegacyState.model_validate(_map_legacy_roles(raw))
    except (json.JSONDecodeError, ValidationError, OSError):
        json_path.rename(json_path.with_suffix(f"{json_path.suffix}.corrupt-{int(time.time())}"))
        return False

    if db.list_records(conn) or db.list_pins(conn):
        json_path.rename(json_path.with_suffix(f"{json_path.suffix}.migrated-{int(time.time())}"))
        return False

    for record in state.records:
        conn.execute(
            "INSERT INTO records (day, big_operations, small_operations, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record.day.isoformat(),
                record.big_operations,
                record.small_operations,
                "",
                db.now_iso(),
            ),
        )
    for pin in state.pins:
        db.add_pin(conn, pin)
    conn.commit()
    json_path.rename(json_path.with_suffix(f"{json_path.suffix}.migrated-{int(time.time())}"))
    return True
