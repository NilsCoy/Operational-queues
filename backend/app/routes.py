from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from . import db
from .auth import bearer_token, find_role, hash_pin, require_role
from .models import PinCode, Role, pin_public_view
from .records import group_by_week, week_end, week_start

router = APIRouter(prefix="/api")

ADMIN = require_role(Role.ADMIN)


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    role: Role


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    conn = request.app.state.db
    pins = await asyncio.to_thread(db.list_pins, conn)
    role = find_role(payload.password, pins)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = request.app.state.sessions.create(role)
    return LoginResponse(token=token, role=role)


@router.post("/logout")
async def logout(request: Request) -> dict:
    token = bearer_token(request)
    if token:
        request.app.state.sessions.revoke(token)
    return {"loggedOut": True}


@router.get("/me")
async def me(request: Request) -> dict:
    token = bearer_token(request)
    role = request.app.state.sessions.role_for(token) if token else None
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing session"
        )
    return {"role": role.value}


class RecordCreate(BaseModel):
    day: date
    big_operations: str = ""
    small_operations: str = ""


class RecordUpdate(BaseModel):
    day: date | None = None
    big_operations: str | None = None
    small_operations: str | None = None


async def _records_payload(request: Request, week_of: date | None, q: str | None) -> dict:
    conn = request.app.state.db
    start = week_start(week_of) if week_of is not None else None
    end = week_end(week_of) if week_of is not None else None
    records = await asyncio.to_thread(db.list_records, conn, start, end, q)
    return {
        "weeks": group_by_week(records),
        "records": [r.model_dump(mode="json") for r in records],
    }


@router.get("/schedule")
async def schedule(
    request: Request,
    week_of: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict:
    """Public schedule (used by /user).

    `week_of` limits the result to that week, `q` keeps only records whose
    big/small operations contain the keyword. Without `week_of` the search
    covers all dates with records.
    """
    return await _records_payload(request, week_of, q)


@router.get("/admin/records", dependencies=[Depends(ADMIN)])
async def read_records(
    request: Request,
    week_of: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict:
    return await _records_payload(request, week_of, q)


@router.post("/admin/records", dependencies=[Depends(ADMIN)])
async def create_record(payload: RecordCreate, request: Request) -> dict:
    conn = request.app.state.db
    record = await asyncio.to_thread(
        db.add_record, conn, payload.day, payload.big_operations, payload.small_operations
    )
    return record.model_dump(mode="json")


@router.put("/admin/records/{record_id}", dependencies=[Depends(ADMIN)])
async def edit_record(record_id: int, payload: RecordUpdate, request: Request) -> dict:
    conn = request.app.state.db
    record = await asyncio.to_thread(
        db.update_record,
        conn,
        record_id,
        payload.day,
        payload.big_operations,
        payload.small_operations,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record not found")
    return record.model_dump(mode="json")


@router.delete("/admin/records/{record_id}", dependencies=[Depends(ADMIN)])
async def remove_record(record_id: int, request: Request) -> dict:
    conn = request.app.state.db
    deleted = await asyncio.to_thread(db.delete_record, conn, record_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record not found")
    return {"deleted": True}


class PinCreate(BaseModel):
    password: str = Field(min_length=4, max_length=128)
    role: Role = Role.USER
    label: str = ""


@router.get("/admin/pins", dependencies=[Depends(ADMIN)])
async def list_pins(request: Request) -> dict:
    conn = request.app.state.db
    pins = await asyncio.to_thread(db.list_pins, conn)
    return {"pins": pin_public_view(pins)}


@router.post("/admin/pins", dependencies=[Depends(ADMIN)])
async def create_pin(payload: PinCreate, request: Request) -> dict:
    conn = request.app.state.db
    password = payload.password
    if len(password.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password must be at least 4 characters",
        )
    pins = await asyncio.to_thread(db.list_pins, conn)
    if find_role(password, pins) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="password already in use")
    pin = PinCode(pin_hash=hash_pin(password), role=payload.role, label=payload.label.strip())
    await asyncio.to_thread(db.add_pin, conn, pin)
    pins = await asyncio.to_thread(db.list_pins, conn)
    return {"pins": pin_public_view(pins)}


@router.delete("/admin/pins/{pin_index}", dependencies=[Depends(ADMIN)])
async def delete_pin(pin_index: int, request: Request) -> dict:
    """Delete a PIN by its position in the list (values/hashes are never exposed)."""
    conn = request.app.state.db

    def _delete() -> list[PinCode] | None:
        pins = db.list_pins(conn)
        if pin_index < 0 or pin_index >= len(pins):
            return None
        removed = pins[pin_index]
        if removed.role == Role.ADMIN and sum(p.role == Role.ADMIN for p in pins) == 1:
            raise ValueError("last admin")
        db.delete_pin(conn, pin_index)
        return db.list_pins(conn)

    try:
        pins = await asyncio.to_thread(_delete)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot delete the last admin password",
        ) from None
    if pins is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pin not found")
    return {"pins": pin_public_view(pins)}
