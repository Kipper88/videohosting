from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from videohosting.db import Subscription, User, Video, get_db_session
from videohosting.services import allowed_image_file
from videohosting.web.utils import redirect_with_flash, template_response

router = APIRouter()


async def _ensure_user(request: Request):
    user = request.state.current_user
    if not user.is_authenticated:
        raise HTTPException(status_code=401)
    return user


@router.get("/u/{username}", name="main.profile")
async def profile(request: Request, username: str, session: AsyncSession = Depends(get_db_session)):
    user = await session.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(status_code=404)

    videos = (
        await session.scalars(
            select(Video)
            .options(selectinload(Video.author))
            .where(Video.user_id == user.id, Video.is_deleted.is_(False), Video.moderation_status == "approved")
            .order_by(Video.created_at.desc())
        )
    ).all()

    viewer = request.state.current_user
    is_subscribed = False
    if viewer.is_authenticated and viewer.id != user.id:
        is_subscribed = (
            await session.scalar(
                select(Subscription).where(
                    Subscription.follower_id == viewer.id,
                    Subscription.followed_id == user.id,
                )
            )
        ) is not None

    subscribers_count = int(
        await session.scalar(select(func.count(Subscription.id)).where(Subscription.followed_id == user.id)) or 0
    )
    subscriptions_count = int(
        await session.scalar(select(func.count(Subscription.id)).where(Subscription.follower_id == user.id)) or 0
    )

    return template_response(
        request,
        "profile.html",
        {
            "profile_user": user,
            "videos": videos,
            "is_subscribed": is_subscribed,
            "subscribers_count": subscribers_count,
            "subscriptions_count": subscriptions_count,
        },
    )


@router.get("/u/{username}/edit", name="main.edit_profile")
async def edit_profile_page(request: Request, username: str, session: AsyncSession = Depends(get_db_session)):
    viewer = await _ensure_user(request)
    user = await session.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(status_code=404)
    if user.id != viewer.id:
        return redirect_with_flash(
            request,
            request.url_for("main.profile", username=username),
            "Можно редактировать только свой профиль.",
            "error",
        )
    return template_response(request, "profile_edit.html", {"profile_user": user})


@router.post("/u/{username}/edit", name="main.edit_profile_post")
async def edit_profile(
    request: Request,
    username: str,
    bio: str = Form(""),
    avatar: UploadFile | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    viewer = await _ensure_user(request)
    user = await session.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(status_code=404)
    if user.id != viewer.id:
        return redirect_with_flash(
            request,
            request.url_for("main.profile", username=username),
            "Можно редактировать только свой профиль.",
            "error",
        )

    user.bio = bio.strip()[:500] or None

    if avatar and avatar.filename:
        if not allowed_image_file(avatar.filename):
            return redirect_with_flash(
                request,
                request.url_for("main.edit_profile", username=username),
                "Недопустимый формат аватара. Разрешены: jpg, jpeg, png, webp.",
                "error",
            )

        avatar_dir = Path(request.app.state.upload_folder) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar_filename = f"{int(datetime.utcnow().timestamp())}_{secure_filename(avatar.filename)}"
        avatar_path = avatar_dir / avatar_filename
        async with aiofiles.open(str(avatar_path), "wb") as out:
            while chunk := await avatar.read(1024 * 1024):
                await out.write(chunk)
        user.avatar_url = f"avatars/{avatar_filename}"

    await session.commit()
    return redirect_with_flash(request, request.url_for("main.profile", username=username), "Профиль обновлён.", "success")


@router.post("/u/{username}/subscribe", name="main.toggle_subscribe")
async def toggle_subscribe(request: Request, username: str, session: AsyncSession = Depends(get_db_session)):
    viewer = await _ensure_user(request)
    user = await session.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(status_code=404)

    if user.id == viewer.id:
        return redirect_with_flash(
            request,
            request.url_for("main.profile", username=username),
            "Нельзя подписаться на себя.",
            "error",
        )

    existing = await session.scalar(
        select(Subscription).where(Subscription.follower_id == viewer.id, Subscription.followed_id == user.id)
    )

    if existing:
        await session.delete(existing)
        message = "Подписка отменена."
    else:
        session.add(Subscription(follower_id=viewer.id, followed_id=user.id))
        message = "Вы подписались на автора."

    await session.commit()
    return redirect_with_flash(request, request.url_for("main.profile", username=username), message, "success")
