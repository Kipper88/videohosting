from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from auth import auth_bp
from config import Config
from identity import resolve_current_user
from main_routes import bp as main_bp
from models import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="YouClone")
    app.add_middleware(SessionMiddleware, secret_key=Config.SECRET_KEY)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    app.state.upload_folder = Config.UPLOAD_FOLDER

    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/uploads", StaticFiles(directory=Config.UPLOAD_FOLDER), name="uploads")

    @app.middleware("http")
    async def bind_current_user(request: Request, call_next):
        request.state.current_user = await resolve_current_user(request)
        return await call_next(request)

    @app.on_event("startup")
    async def on_startup() -> None:
        await init_db()

    app.include_router(main_bp)
    app.include_router(auth_bp)
    return app


app = create_app()
