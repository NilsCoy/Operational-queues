from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"


class OperationRecord(BaseModel):
    """One row of the weekly schedule: a date plus big and small operations."""

    id: int
    day: date
    big_operations: str = ""
    small_operations: str = ""


class PinCode(BaseModel):
    """A PIN the admin issues, bound to a role (admin or user).

    Only the hash is stored; the plain PIN is shown once at creation time.
    """

    pin_hash: str
    role: Role = Role.USER
    label: str = ""


class AppState(BaseModel):
    records: list[OperationRecord] = Field(default_factory=list)
    next_record_id: int = 1
    pins: list[PinCode] = Field(default_factory=list)


def pin_public_view(state: AppState) -> list[dict]:
    """PIN list for the admin UI. Hashes are never exposed."""
    return [
        {"role": p.role.value, "label": p.label, "hash_prefix": p.pin_hash[:12]}
        for p in state.pins
    ]


def has_role(state: AppState, role: Role) -> bool:
    return any(p.role == role for p in state.pins)