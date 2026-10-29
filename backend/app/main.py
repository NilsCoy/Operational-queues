from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .auth import SessionStore, has_admin, hash_pin
from .models import PinCode, Role
from .routes import router
from .store import migrate_from_json

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "app.db"
LEGACY_STATE_PATH = BASE_DIR / "data" / "state.json"
FRONTEND_DIR = BASE_DIR / "frontend"


def create_app(data_path: Path) -> FastAPI:
    app = FastAPI(title="Operational Queues")
    conn = db.init_db(data_path)
    if LEGACY_STATE_PATH.exists():
        migrate_from_json(conn, LEGACY_STATE_PATH)
    app.state.db = conn
    app.state.sessions = SessionStore()
    app.include_router(router)

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/frontend/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/bootstrap")
    async def bootstrap_status(request: Request) -> dict:
        pins = await asyncio.to_thread(db.list_pins, request.app.state.db)
        return {"has_admin": has_admin(pins)}

    @app.post("/api/bootstrap/admin")
    async def bootstrap_admin(request: Request):
        conn = request.app.state.db
        pins = await asyncio.to_thread(db.list_pins, conn)
        if has_admin(pins):
            return JSONResponse(status_code=409, content={"detail": "admin already exists"})
        body = await request.json()
        password = str(body.get("password", ""))
        if len(password.strip()) < 4:
            return JSONResponse(
                status_code=400,
                content={"detail": "password must be at least 4 characters"},
            )
        pin = PinCode(pin_hash=hash_pin(password), role=Role.ADMIN, label="Admin")
        await asyncio.to_thread(db.add_pin, conn, pin)
        return {"has_admin": True}

    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

    def page_handler(page_name: str):
        async def handler():
            index = FRONTEND_DIR / page_name / "index.html"
            if not index.exists():
                return JSONResponse(status_code=404, content={"detail": "page not found"})
            return FileResponse(index)

        return handler

    app.add_api_route("/", page_handler("user"), methods=["GET"])
    app.add_api_route("/user", page_handler("user"), methods=["GET"])
    app.add_api_route("/admin", page_handler("admin"), methods=["GET"])

    return app


app = create_app(DEFAULT_DATA_PATH)
