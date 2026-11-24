from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    USER = "reader"


class OperationRecord(BaseModel):
    """One row of the weekly schedule: a date plus big and small operations.

    created_by / created_at are written once, when the record is added to the journal.
    """

    id: int
    day: date
    big_operations: str = ""
    small_operations: str = ""
    created_by: str = ""
    created_at: str = ""


class PinCode(BaseModel):
    """An access password the admin issues, bound to a role (admin, editor or user).

    Only the hash is stored; the plain password is shown once at creation time.
    created_at / changed_at are ISO timestamps; the password must be changed every 3 months.
    """

    id: int = 0
    pin_hash: str
    role: Role = Role.USER
    label: str = ""
    created_at: str = ""
    changed_at: str = ""


def pin_public_view(pins: list[PinCode]) -> list[dict]:
    """PIN list for the admin UI. Hashes are never exposed."""
    return [{"role": p.role.value, "label": p.label, "hash_prefix": p.pin_hash[:12]} for p in pins]


def has_role(pins: list[PinCode], role: Role) -> bool:
    return any(p.role == role for p in pins)
