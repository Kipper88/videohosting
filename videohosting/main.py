from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from videohosting.api import api_router
from videohosting.core.config import Config
from videohosting.db import init_db
from videohosting.services.identity import resolve_current_user


def create_app() -> FastAPI:
    app = FastAPI(title="Movier")
    app.add_middleware(SessionMiddleware, secret_key=Config.SECRET_KEY)

    upload_path = Path(Config.UPLOAD_FOLDER)
    upload_path.mkdir(parents=True, exist_ok=True)
    app.state.upload_folder = str(upload_path)

    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

    @app.middleware("http")
    async def bind_current_user(request: Request, call_next):
        request.state.current_user = await resolve_current_user(request)
        return await call_next(request)

    @app.on_event("startup")
    async def on_startup() -> None:
        await init_db()

    app.include_router(api_router)
    return app


app = create_app()
