from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from videohosting.db import User, get_db_session
from videohosting.web.utils import redirect_with_flash, template_response

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/auth")


@router.get("/register", name="auth.register")
async def register_page(request: Request):
    if getattr(request.state.current_user, "is_authenticated", False):
        return RedirectResponse(url=request.url_for("main.index"), status_code=303)
    return template_response(request, "auth_register.html", {})


@router.post("/register", name="auth.register_post")
async def register(
    request: Request,
    username: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
):
    username = username.strip()
    email = email.strip().lower()

    if not username or not email or not password:
        return redirect_with_flash(request, request.url_for("auth.register"), "Заполните все поля.", "error")

    if password != password2:
        return redirect_with_flash(request, request.url_for("auth.register"), "Пароли не совпадают.", "error")

    existing = await session.scalar(select(User).where(or_(User.username == username, User.email == email)))
    if existing:
        msg = (
            "Пользователь с таким ником уже существует."
            if existing.username == username
            else "Пользователь с таким email уже существует."
        )
        return redirect_with_flash(request, request.url_for("auth.register"), msg, "error")

    session.add(User(username=username, email=email, password_hash=pwd_context.hash(password)))
    await session.commit()
    return redirect_with_flash(
        request,
        request.url_for("auth.login"),
        "Регистрация прошла успешно. Теперь вы можете войти.",
        "success",
    )


@router.get("/login", name="auth.login")
async def login_page(request: Request):
    if getattr(request.state.current_user, "is_authenticated", False):
        return RedirectResponse(url=request.url_for("main.index"), status_code=303)
    return template_response(request, "auth_login.html", {})


@router.post("/login", name="auth.login_post")
async def login(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
):
    login = login.strip()
    user = await session.scalar(select(User).where(or_(User.email == login.lower(), User.username == login)))

    if not user or not pwd_context.verify(password, user.password_hash):
        return redirect_with_flash(request, request.url_for("auth.login"), "Неверный логин или пароль.", "error")

    request.session["user_id"] = user.id
    return redirect_with_flash(request, request.url_for("main.index"), "Вы вошли в аккаунт.", "success")


@router.get("/logout", name="auth.logout")
async def logout(request: Request):
    request.session.pop("user_id", None)
    return redirect_with_flash(request, request.url_for("main.index"), "Вы вышли из аккаунта.", "success")
