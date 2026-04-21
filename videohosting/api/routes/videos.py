from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from videohosting.core.config import Config
from videohosting.db import Report, UserRole, Video, VideoReaction, get_db_session
from videohosting.services import allowed_file, generate_thumbnail, get_video_duration
from videohosting.use_cases.video import (
    add_comment,
    get_comments_tree,
    get_related_videos,
    get_shorts_feed,
    register_view,
    toggle_comment_reaction,
    toggle_reaction,
)
from videohosting.web.utils import redirect_with_flash, template_response

router = APIRouter()
REPORT_REASONS = ("Спам", "Оскорбление", "Неприемлемый контент", "Нарушение авторских прав")


async def _ensure_user(request: Request):
    user = request.state.current_user
    if not user.is_authenticated:
        raise HTTPException(status_code=401)
    return user


@router.get("/upload", name="main.upload")
async def upload_page(request: Request):
    await _ensure_user(request)
    return template_response(request, "upload.html", {})


@router.post("/upload", name="main.upload_post")
async def upload(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    tags: str = Form(""),
    file: UploadFile | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    user = await _ensure_user(request)
    title = title.strip()
    description = description.strip()
    tags = ",".join({tag.strip().lower() for tag in tags.split(",") if tag.strip()})

    if not title:
        return redirect_with_flash(request, request.url_for("main.upload"), "Введите название видео.", "error")

    if not file or not file.filename:
        return redirect_with_flash(request, request.url_for("main.upload"), "Выберите видеофайл.", "error")

    if not allowed_file(file.filename):
        return redirect_with_flash(
            request,
            request.url_for("main.upload"),
            "Недопустимый формат файла. Разрешены: mp4, webm, ogg, mov.",
            "error",
        )

    filename = f"{int(datetime.utcnow().timestamp())}_{secure_filename(file.filename)}"
    upload_dir = Path(request.app.state.upload_folder)
    save_path = upload_dir / filename

    async with aiofiles.open(str(save_path), "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)

    thumb_filename = f"{filename}.jpg"
    thumb_path = upload_dir / thumb_filename
    thumbnail_ok = await generate_thumbnail(str(save_path), str(thumb_path))
    duration = await get_video_duration(str(save_path))
    is_short = bool(duration and duration <= 60)

    status = "pending" if Config.MANUAL_MODERATION else "approved"
    video = Video(
        user_id=user.id,
        title=title,
        description=description,
        filename=filename,
        thumbnail_filename=thumb_filename if thumbnail_ok else None,
        moderation_status=status,
        tags=tags or None,
        duration_seconds=duration,
        is_short=is_short,
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)

    success_message = "Видео отправлено на ручную модерацию." if status == "pending" else "Видео опубликовано."
    return redirect_with_flash(
        request,
        request.url_for("main.video_detail", video_id=video.id),
        success_message,
        "success",
    )


@router.get("/video/{video_id}", name="main.video_detail")
async def video_detail(request: Request, video_id: int, session: AsyncSession = Depends(get_db_session)):
    video = await session.scalar(select(Video).options(selectinload(Video.author)).where(Video.id == video_id))
    if not video or video.is_deleted:
        raise HTTPException(status_code=404)

    user = request.state.current_user
    if video.moderation_status != "approved" and (not user.is_authenticated or user.role not in {UserRole.MODERATOR.value, UserRole.ADMIN.value}):
        return redirect_with_flash(request, request.url_for("main.index"), "Видео пока на модерации.", "error")

    video.views += 1
    await session.commit()

    if user.is_authenticated:
        await register_view(user.id, video.id)

    user_reaction = 0
    if user.is_authenticated:
        reaction = await session.scalar(
            select(VideoReaction).where(VideoReaction.user_id == user.id, VideoReaction.video_id == video.id)
        )
        user_reaction = reaction.value if reaction else 0

    comments_tree = await get_comments_tree(video.id)
    related_videos = await get_related_videos(video.id, video.tags)
    return template_response(
        request,
        "video_detail.html",
        {
            "video": video,
            "comments_tree": comments_tree,
            "related_videos": related_videos,
            "user_reaction": user_reaction,
            "report_reasons": REPORT_REASONS,
        },
    )


@router.post("/video/{video_id}/comments", name="main.video_comment")
async def video_comment(
    request: Request,
    video_id: int,
    text: str = Form(""),
    parent_id: int | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _ensure_user(request)
    exists = await session.get(Video, video_id)
    if not exists or exists.is_deleted:
        raise HTTPException(status_code=404)

    ok = await add_comment(video_id, user.id, text, parent_id=parent_id)
    msg = "Комментарий добавлен." if ok else "Комментарий пустой или родитель не найден."
    return redirect_with_flash(
        request,
        request.url_for("main.video_detail", video_id=video_id),
        msg,
        "success" if ok else "error",
    )


@router.post("/api/comments/{comment_id}/react", name="main.comment_react")
async def comment_react(request: Request, comment_id: int):
    user = await _ensure_user(request)
    payload = await request.json()
    action = payload.get("action")
    if action not in {"like", "dislike"}:
        return JSONResponse({"error": "invalid_action"}, status_code=400)
    likes, dislikes, user_reaction = await toggle_comment_reaction(comment_id, user.id, action)
    return JSONResponse({"likes": likes, "dislikes": dislikes, "user_reaction": user_reaction})


@router.post("/video/{video_id}/report", name="main.video_report")
async def report_video(
    request: Request,
    video_id: int,
    reason: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _ensure_user(request)
    if reason not in REPORT_REASONS:
        return redirect_with_flash(request, request.url_for("main.video_detail", video_id=video_id), "Неверная причина жалобы.", "error")
    video = await session.get(Video, video_id)
    if not video or video.is_deleted:
        raise HTTPException(status_code=404)
    session.add(Report(user_id=user.id, video_id=video_id, reason=reason))
    await session.commit()
    return redirect_with_flash(request, request.url_for("main.video_detail", video_id=video_id), "Жалоба отправлена.", "success")


@router.post("/video/{video_id}/delete", name="main.video_delete")
async def video_delete(
    request: Request,
    video_id: int,
    deletion_reason: str = Form("Удалено автором"),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _ensure_user(request)
    video = await session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404)

    can_moderate = user.role in {UserRole.MODERATOR.value, UserRole.ADMIN.value}
    if video.user_id != user.id and not can_moderate:
        return redirect_with_flash(
            request,
            request.url_for("main.video_detail", video_id=video.id),
            "Недостаточно прав для удаления.",
            "error",
        )

    video.is_deleted = True
    video.deletion_reason = deletion_reason.strip()[:500] or "Удалено"
    await session.commit()
    return redirect_with_flash(request, request.url_for("main.index"), "Видео скрыто и помечено удалённым.", "success")


@router.get("/uploads/{filename:path}", name="main.uploaded_file")
async def uploaded_file(request: Request, filename: str):
    return RedirectResponse(url=request.url_for("uploads", path=filename), status_code=307)


@router.post("/api/videos/{video_id}/react", name="main.video_react")
async def video_react(request: Request, video_id: int, session: AsyncSession = Depends(get_db_session)):
    user = await _ensure_user(request)
    video = await session.get(Video, video_id)
    if not video or video.is_deleted:
        raise HTTPException(status_code=404)

    payload = await request.json()
    action = payload.get("action")
    if action not in {"like", "dislike"}:
        return JSONResponse({"error": "invalid_action"}, status_code=400)

    likes, dislikes, user_reaction = await toggle_reaction(video.id, user.id, action)
    return JSONResponse({"likes": likes, "dislikes": dislikes, "user_reaction": user_reaction})


@router.get("/shorts", name="main.shorts")
async def shorts_page(request: Request):
    return template_response(request, "shorts.html", {})


@router.get("/api/shorts", name="main.shorts_api")
async def shorts_api(offset: int = 0, limit: int = 8):
    items = await get_shorts_feed(offset=offset, limit=min(limit, 20))
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "filename": item.filename,
            "author": item.author.username if item.author else "Аноним",
            "views": item.views,
        }
        for item in items
    ]
    return JSONResponse({"items": payload})
