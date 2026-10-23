from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import SessionStore, has_admin, hash_pin
from .models import PinCode, Role
from .routes import router
from .store import load_state, save_state

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "state.json"
FRONTEND_DIR = BASE_DIR / "frontend"


def create_app(data_path: Path) -> FastAPI:
    app = FastAPI(title="Operational Queues")
    app.state.data_path = data_path
    app.state.queue_state = load_state(data_path)
    app.state.lock = asyncio.Lock()
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
        return {"has_admin": has_admin(request.app.state.queue_state)}

    @app.post("/api/bootstrap/admin")
    async def bootstrap_admin(request: Request):
        state = request.app.state.queue_state
        if has_admin(state):
            return JSONResponse(
                status_code=409, content={"detail": "admin already exists"}
            )
        body = await request.json()
        password = str(body.get("password", ""))
        if len(password.strip()) < 4:
            return JSONResponse(
                status_code=400,
                content={"detail": "password must be at least 4 characters"},
            )
        async with request.app.state.lock:
            state.pins.append(
                PinCode(pin_hash=hash_pin(password), role=Role.ADMIN, label="Admin")
            )
            await asyncio.to_thread(save_state, app.state.data_path, state)
        return {"has_admin": True}

    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

    def page_handler(page_name: str):
        async def handler():
            index = FRONTEND_DIR / page_name / "index.html"
            if not index.exists():
                return JSONResponse(
                    status_code=404, content={"detail": "page not found"}
                )
            return FileResponse(index)

        return handler

    app.add_api_route("/", page_handler("user"), methods=["GET"])
    app.add_api_route("/user", page_handler("user"), methods=["GET"])
    app.add_api_route("/admin", page_handler("admin"), methods=["GET"])

    return app


app = create_app(DEFAULT_DATA_PATH)
