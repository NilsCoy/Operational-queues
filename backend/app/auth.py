from __future__ import annotations

import calendar
import hashlib
import hmac
import random
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, Request, status

from .models import PinCode, Role

PBKDF2_ITERATIONS = 120_000
PBKDF2_ALGO = "sha256"

PASSWORD_MIN_LENGTH = 12
PASSWORD_SPECIALS = "!@#$%^&*()-_=+[]{};:,.?/\\|~"
PASSWORD_MAX_AGE_MONTHS = 3


def password_policy_error(password: str) -> str | None:
    """Return a human-readable reason if `password` breaks the policy, else None.

    Rules: at least 12 characters, at least one uppercase letter and at least
    one special character (anything that is not a letter, digit or space).
    Spaces are allowed anywhere in the password.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"пароль должен содержать минимум {PASSWORD_MIN_LENGTH} символов"
    if not any(ch.isupper() for ch in password):
        return "пароль должен содержать хотя бы одну заглавную букву"
    if not any(not ch.isalnum() and not ch.isspace() for ch in password):
        return "пароль должен содержать хотя бы один специальный символ"
    return None


def generate_password(length: int = 14) -> str:
    """Random password that always satisfies `password_policy_error`."""
    length = max(length, PASSWORD_MIN_LENGTH)
    alphabet = string.ascii_letters + string.digits + PASSWORD_SPECIALS
    rng = random.SystemRandom()
    while True:
        chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(PASSWORD_SPECIALS),
        ]
        chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
        rng.shuffle(chars)
        candidate = "".join(chars)
        if password_policy_error(candidate) is None:
            return candidate


def password_expired(changed_at: str, now: datetime | None = None) -> bool:
    """True when the password was last changed PASSWORD_MAX_AGE_MONTHS or more ago."""
    if not changed_at:
        return True
    changed = datetime.fromisoformat(changed_at)
    now = now or datetime.now()
    month_index = changed.month - 1 + PASSWORD_MAX_AGE_MONTHS
    year = changed.year + month_index // 12
    month = month_index % 12 + 1
    day = min(changed.day, calendar.monthrange(year, month)[1])
    due = changed.replace(year=year, month=month, day=day)
    return now >= due


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


def find_pin(pin: str, pins: list[PinCode]) -> PinCode | None:
    """Return the stored entry whose password matches `pin`, or None."""
    for entry in pins:
        if verify_pin(pin, entry.pin_hash):
            return entry
    return None


def has_admin(pins: list[PinCode]) -> bool:
    return any(p.role == Role.ADMIN for p in pins)


@dataclass(frozen=True)
class Session:
    role: Role
    pin_id: int


class SessionStore:
    def __init__(self) -> None:
        self._tokens: dict[str, Session] = {}

    def create(self, role: Role, pin_id: int) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = Session(role=role, pin_id=pin_id)
        return token

    def get(self, token: str) -> Session | None:
        return self._tokens.get(token)

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)

    def revoke_pin(self, pin_id: int) -> None:
        """Drop every session opened with the given password (e.g. after deletion)."""
        for token in [t for t, s in self._tokens.items() if s.pin_id == pin_id]:
            del self._tokens[token]


def bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    return header.removeprefix("Bearer ").strip()


def require_roles(*roles: Role) -> Callable:
    """Dependency: 401 without a valid session, 403 if the role is not allowed."""

    async def dependency(request: Request) -> None:
        token = bearer_token(request)
        sessions: SessionStore = request.app.state.sessions
        session = sessions.get(token) if token else None
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing session",
            )
        if session.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden for this role",
            )

    return dependency
