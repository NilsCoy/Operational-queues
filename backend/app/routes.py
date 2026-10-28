from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from .auth import bearer_token, find_role, hash_pin, require_role
from .models import PinCode, Role, pin_public_view
from .records import (
    add_record,
    delete_record,
    group_by_week,
    list_records,
    update_record,
)
from .store import save_state

router = APIRouter(prefix="/api")

ADMIN = require_role(Role.ADMIN)


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    role: Role


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    state = request.app.state.queue_state
    role = find_role(payload.password, state)
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


async def _persist(request: Request) -> None:
    await asyncio.to_thread(save_state, request.app.state.data_path, request.app.state.queue_state)


class RecordCreate(BaseModel):
    day: date
    big_operations: str = ""
    small_operations: str = ""


class RecordUpdate(BaseModel):
    day: date | None = None
    big_operations: str | None = None
    small_operations: str | None = None


@router.get("/schedule")
async def schedule(
    request: Request,
    week_of: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict:
    """Public schedule (used by /user). `week_of` limits the result to that week,
    `q` keeps only records whose big/small operations contain the keyword.
    Without `week_of` the search covers all dates with records."""
    state = request.app.state.queue_state
    records = list_records(state, week_of, q)
    return {
        "weeks": group_by_week(records),
        "records": [r.model_dump(mode="json") for r in records],
    }


@router.get("/admin/records", dependencies=[Depends(ADMIN)])
async def read_records(
    request: Request,
    week_of: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict:
    state = request.app.state.queue_state
    records = list_records(state, week_of, q)
    return {
        "weeks": group_by_week(records),
        "records": [r.model_dump(mode="json") for r in records],
    }


@router.post("/admin/records", dependencies=[Depends(ADMIN)])
async def create_record(payload: RecordCreate, request: Request) -> dict:
    async with request.app.state.lock:
        record = add_record(
            request.app.state.queue_state,
            payload.day,
            payload.big_operations,
            payload.small_operations,
        )
        await _persist(request)
    return record.model_dump(mode="json")


@router.put("/admin/records/{record_id}", dependencies=[Depends(ADMIN)])
async def edit_record(record_id: int, payload: RecordUpdate, request: Request) -> dict:
    async with request.app.state.lock:
        record = update_record(
            request.app.state.queue_state,
            record_id,
            payload.day,
            payload.big_operations,
            payload.small_operations,
        )
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record not found")
        await _persist(request)
    return record.model_dump(mode="json")


@router.delete("/admin/records/{record_id}", dependencies=[Depends(ADMIN)])
async def remove_record(record_id: int, request: Request) -> dict:
    async with request.app.state.lock:
        deleted = delete_record(request.app.state.queue_state, record_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record not found")
        await _persist(request)
    return {"deleted": True}


class PinCreate(BaseModel):
    password: str = Field(min_length=4, max_length=128)
    role: Role = Role.USER
    label: str = ""


@router.get("/admin/pins", dependencies=[Depends(ADMIN)])
async def list_pins(request: Request) -> dict:
    return {"pins": pin_public_view(request.app.state.queue_state)}


@router.post("/admin/pins", dependencies=[Depends(ADMIN)])
async def create_pin(payload: PinCreate, request: Request) -> dict:
    state = request.app.state.queue_state
    password = payload.password
    if len(password.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password must be at least 4 characters",
        )
    if find_role(password, state) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="password already in use")
    async with request.app.state.lock:
        state.pins.append(
            PinCode(pin_hash=hash_pin(password), role=payload.role, label=payload.label.strip())
        )
        await _persist(request)
    return {"pins": pin_public_view(state)}


@router.delete("/admin/pins/{pin_index}", dependencies=[Depends(ADMIN)])
async def delete_pin(pin_index: int, request: Request) -> dict:
    """Delete a PIN by its position in the list (values/hashes are never exposed)."""
    state = request.app.state.queue_state
    async with request.app.state.lock:
        if pin_index < 0 or pin_index >= len(state.pins):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pin not found")
        removed = state.pins.pop(pin_index)
        if removed.role == Role.ADMIN and not any(p.role == Role.ADMIN for p in state.pins):
            state.pins.insert(pin_index, removed)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot delete the last admin password",
            )
        await _persist(request)
    return {"pins": pin_public_view(state)}
