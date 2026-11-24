from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import OperationRecord, PinCode, Role

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    big_operations TEXT NOT NULL DEFAULT '',
    small_operations TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pin_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    changed_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_records_day ON records (day);
"""

# Columns added after the first release: (table, column, definition).
# CREATE TABLE IF NOT EXISTS does not add them to an existing database.
MIGRATIONS = [
    ("records", "created_by", "TEXT NOT NULL DEFAULT ''"),
    ("records", "created_at", "TEXT NOT NULL DEFAULT ''"),
    ("pins", "created_at", "TEXT NOT NULL DEFAULT ''"),
    ("pins", "changed_at", "TEXT NOT NULL DEFAULT ''"),
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, definition in MIGRATIONS:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    # Pins that existed before timestamps were added count as created and changed now.
    stamp = now_iso()
    conn.execute("UPDATE pins SET created_at = ? WHERE created_at = ''", (stamp,))
    conn.execute("UPDATE pins SET changed_at = created_at WHERE changed_at = ''")


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


def _row_to_record(row: sqlite3.Row) -> OperationRecord:
    return OperationRecord(
        id=row["id"],
        day=date.fromisoformat(row["day"]),
        big_operations=row["big_operations"],
        small_operations=row["small_operations"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_pin(row: sqlite3.Row) -> PinCode:
    return PinCode(
        id=row["id"],
        pin_hash=row["pin_hash"],
        role=Role(row["role"]),
        label=row["label"],
        created_at=row["created_at"],
        changed_at=row["changed_at"],
    )


# --- records ---------------------------------------------------------------


def list_records(
    conn: sqlite3.Connection,
    start: date | None = None,
    end: date | None = None,
    q: str | None = None,
) -> list[OperationRecord]:
    sql = "SELECT * FROM records"
    clauses: list[str] = []
    params: list = []
    if start is not None:
        clauses.append("day >= ?")
        params.append(start.isoformat())
    if end is not None:
        clauses.append("day <= ?")
        params.append(end.isoformat())
    needle = (q or "").strip().lower()
    if needle:
        clauses.append(
            "(instr(lower(big_operations), ?) > 0 OR instr(lower(small_operations), ?) > 0)"
        )
        params.extend([needle, needle])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY day, id"
    return [_row_to_record(row) for row in conn.execute(sql, params)]


def get_record(conn: sqlite3.Connection, record_id: int) -> OperationRecord | None:
    row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    return _row_to_record(row) if row else None


def add_record(
    conn: sqlite3.Connection,
    day: date,
    big_operations: str = "",
    small_operations: str = "",
    created_by: str = "",
) -> OperationRecord:
    cur = conn.execute(
        "INSERT INTO records (day, big_operations, small_operations, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (day.isoformat(), big_operations, small_operations, created_by, now_iso()),
    )
    conn.commit()
    record = get_record(conn, int(cur.lastrowid))
    assert record is not None
    return record


def update_record(
    conn: sqlite3.Connection,
    record_id: int,
    day: date | None = None,
    big_operations: str | None = None,
    small_operations: str | None = None,
) -> OperationRecord | None:
    existing = get_record(conn, record_id)
    if existing is None:
        return None
    conn.execute(
        "UPDATE records SET day = ?, big_operations = ?, small_operations = ? WHERE id = ?",
        (
            (day or existing.day).isoformat(),
            existing.big_operations if big_operations is None else big_operations,
            existing.small_operations if small_operations is None else small_operations,
            record_id,
        ),
    )
    conn.commit()
    return get_record(conn, record_id)


def delete_record(conn: sqlite3.Connection, record_id: int) -> bool:
    cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    return cur.rowcount > 0


# --- pins ------------------------------------------------------------------


def list_pins(conn: sqlite3.Connection) -> list[PinCode]:
    return [_row_to_pin(row) for row in conn.execute("SELECT * FROM pins ORDER BY id")]


def add_pin(conn: sqlite3.Connection, pin: PinCode) -> None:
    # A new password counts as created and changed at the same moment.
    stamp = now_iso()
    conn.execute(
        "INSERT INTO pins (pin_hash, role, label, created_at, changed_at) VALUES (?, ?, ?, ?, ?)",
        (pin.pin_hash, pin.role.value, pin.label, stamp, stamp),
    )
    conn.commit()


def update_pin_hash(conn: sqlite3.Connection, pin_id: int, pin_hash: str) -> None:
    conn.execute(
        "UPDATE pins SET pin_hash = ?, changed_at = ? WHERE id = ?",
        (pin_hash, now_iso(), pin_id),
    )
    conn.commit()


def delete_pin(conn: sqlite3.Connection, pin_index: int) -> PinCode | None:
    """Delete by 0-based position in the pins list; returns the removed pin."""
    rows = conn.execute("SELECT id FROM pins ORDER BY id").fetchall()
    if pin_index < 0 or pin_index >= len(rows):
        return None
    pin_id = rows[pin_index]["id"]
    row = conn.execute("SELECT * FROM pins WHERE id = ?", (pin_id,)).fetchone()
    assert row is not None
    conn.execute("DELETE FROM pins WHERE id = ?", (pin_id,))
    conn.commit()
    return _row_to_pin(row)
