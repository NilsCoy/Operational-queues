from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from .models import AppState, Role

PBKDF2_ITERATIONS = 120_000
PBKDF2_ALGO = "sha256"


def hash_pin(pin: str) -> str:
    """Hash a PIN/password with PBKDF2-HMAC-SHA256 and a random salt.

    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(PBKDF2_ALGO, pin.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_{PBKDF2_ALGO}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    """Constant-time check of a PIN against its stored PBKDF2 hash."""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if not algo.startswith("pbkdf2_"):
            return False
        digest = hashlib.pbkdf2_hmac(
            algo.removeprefix("pbkdf2_"),
            pin.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def find_role(pin: str, state: AppState) -> Role | None:
    """Return the role bound to `pin`, or None if no stored hash matches."""
    for entry in state.pins:
        if verify_pin(pin, entry.pin_hash):
            return entry.role
    return None


def has_admin(state: AppState) -> bool:
    return any(p.role == Role.ADMIN for p in state.pins)


class SessionStore:
    def __init__(self) -> None:
        self._tokens: dict[str, Role] = {}

    def create(self, role: Role) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = role
        return token

    def role_for(self, token: str) -> Role | None:
        return self._tokens.get(token)

    def is_valid(self, token: str, role: Role) -> bool:
        return self._tokens.get(token) == role

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)

    def revoke_role(self, role: Role) -> None:
        for token in [t for t, r in self._tokens.items() if r == role]:
            del self._tokens[token]


def bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    return header.removeprefix("Bearer ").strip()


def require_role(role: Role) -> Callable:
    async def dependency(request: Request) -> None:
        token = bearer_token(request)
        sessions: SessionStore = request.app.state.sessions
        if not token or not sessions.is_valid(token, role):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing session",
            )

    return dependency


async def require_any(request: Request) -> Role:
    token = bearer_token(request)
    sessions: SessionStore = request.app.state.sessions
    role = sessions.role_for(token) if token else None
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing session",
        )
    return role
