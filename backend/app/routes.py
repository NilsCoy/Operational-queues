from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from . import db
from .auth import (
    bearer_token,
    find_pin,
    generate_password,
    hash_pin,
    password_expired,
    password_policy_error,
    require_roles,
    verify_pin,
)
from .models import PinCode, Role, pin_public_view
from .records import group_by_week, week_end, week_start

router = APIRouter(prefix="/api")

# Admin: everything. Editor: admin panel and journal records, but no access passwords.
ADMIN = require_roles(Role.ADMIN)
STAFF = require_roles(Role.ADMIN, Role.EDITOR)


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    role: Role
    password_expired: bool = False


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    conn = request.app.state.db
    pins = await asyncio.to_thread(db.list_pins, conn)
    pin = find_pin(payload.password, pins)
    if pin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = request.app.state.sessions.create(pin.role, pin.id)
    return LoginResponse(
        token=token,
        role=pin.role,
        password_expired=password_expired(pin.changed_at),
    )


@router.post("/logout")
async def logout(request: Request) -> dict:
    token = bearer_token(request)
    if token:
        request.app.state.sessions.revoke(token)
    return {"loggedOut": True}


async def _current_pin(request: Request) -> PinCode:
    """The password behind the current session; 401 if the session is missing or stale."""
    token = bearer_token(request)
    session = request.app.state.sessions.get(token) if token else None
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing session"
        )
    pins = await asyncio.to_thread(db.list_pins, request.app.state.db)
    pin = next((p for p in pins if p.id == session.pin_id), None)
    if pin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing session"
        )
    return pin


@router.get("/me")
async def me(request: Request) -> dict:
    pin = await _current_pin(request)
    return {
        "role": pin.role.value,
        "password_expired": password_expired(pin.changed_at),
    }


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
async def change_password(payload: PasswordChange, request: Request) -> dict:
    """Change the password of the current session (any role)."""
    pin = await _current_pin(request)
    conn = request.app.state.db
    if not verify_pin(payload.current_password, pin.pin_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="текущий пароль неверен")
    error = password_policy_error(payload.new_password)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="новый пароль должен отличаться от текущего",
        )
    pins = await asyncio.to_thread(db.list_pins, conn)
    if find_pin(payload.new_password, pins) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="password already in use")
    # update_pin_hash also stamps changed_at, which restarts the 3-month countdown.
    await asyncio.to_thread(db.update_pin_hash, conn, pin.id, hash_pin(payload.new_password))
    return {"changed": True, "password_expired": False}


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


@router.get("/admin/records", dependencies=[Depends(STAFF)])
async def read_records(
    request: Request,
    week_of: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict:
    return await _records_payload(request, week_of, q)


@router.post("/admin/records", dependencies=[Depends(STAFF)])
async def create_record(payload: RecordCreate, request: Request) -> dict:
    # A journal entry needs at least one filled operations field.
    if not payload.big_operations.strip() and not payload.small_operations.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="заполните хотя бы одно поле: крупные или мелкие операции",
        )
    pin = await _current_pin(request)
    conn = request.app.state.db
    record = await asyncio.to_thread(
        db.add_record,
        conn,
        payload.day,
        payload.big_operations,
        payload.small_operations,
        pin.label or pin.role.value,
    )
    return record.model_dump(mode="json")


@router.put("/admin/records/{record_id}", dependencies=[Depends(STAFF)])
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


@router.delete("/admin/records/{record_id}", dependencies=[Depends(STAFF)])
async def remove_record(record_id: int, request: Request) -> dict:
    conn = request.app.state.db
    deleted = await asyncio.to_thread(db.delete_record, conn, record_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record not found")
    return {"deleted": True}


class PinCreate(BaseModel):
    # Empty password -> the server generates one and returns it once.
    password: str = Field(default="", max_length=128)
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
    generated: str | None = None
    if password:
        error = password_policy_error(password)
        if error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    else:
        generated = generate_password()
        password = generated
    pins = await asyncio.to_thread(db.list_pins, conn)
    if find_pin(password, pins) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="password already in use")
    pin = PinCode(pin_hash=hash_pin(password), role=payload.role, label=payload.label.strip())
    await asyncio.to_thread(db.add_pin, conn, pin)
    pins = await asyncio.to_thread(db.list_pins, conn)
    result: dict = {"pins": pin_public_view(pins)}
    if generated is not None:
        result["generated_password"] = generated
    return result


@router.delete("/admin/pins/{pin_index}", dependencies=[Depends(ADMIN)])
async def delete_pin(pin_index: int, request: Request) -> dict:
    """Delete a password by its position in the list (values/hashes are never exposed)."""
    conn = request.app.state.db

    def _delete() -> tuple[int, list[PinCode]] | None:
        pins = db.list_pins(conn)
        if pin_index < 0 or pin_index >= len(pins):
            return None
        removed = pins[pin_index]
        if removed.role == Role.ADMIN and sum(p.role == Role.ADMIN for p in pins) == 1:
            raise ValueError("last admin")
        db.delete_pin(conn, pin_index)
        return removed.id, db.list_pins(conn)

    try:
        result = await asyncio.to_thread(_delete)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot delete the last admin password",
        ) from None
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pin not found")
    removed_id, pins = result
    request.app.state.sessions.revoke_pin(removed_id)
    return {"pins": pin_public_view(pins)}
