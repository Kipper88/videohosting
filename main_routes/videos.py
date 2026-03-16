from __future__ import annotations

import os
from datetime import datetime

import aiofiles
from fastapi import Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from models import Video, VideoComment, VideoReaction, get_db_session
from services import allowed_file, generate_thumbnail, moderate_thumbnail_with_ai, moderate_video_content_with_ai
from video_logic import add_comment, get_related_videos, toggle_reaction
from web_utils import redirect_with_flash, template_response

from .blueprint import bp
from .helpers import remove_files


async def _ensure_user(request: Request):
    user = request.state.current_user
    if not user.is_authenticated:
        raise HTTPException(status_code=401)
    return user


@bp.get("/upload", name="main.upload")
async def upload_page(request: Request):
    await _ensure_user(request)
    return template_response(request, "upload.html", {})


@bp.post("/upload", name="main.upload_post")
async def upload(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    file: UploadFile | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    user = await _ensure_user(request)
    title = title.strip()
    description = description.strip()

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
    save_path = os.path.join(request.app.state.upload_folder, filename)

    async with aiofiles.open(save_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)

    thumb_filename = f"{filename}.jpg"
    thumb_path = os.path.join(request.app.state.upload_folder, thumb_filename)
    thumbnail_ok = await generate_thumbnail(save_path, thumb_path)

    try:
        is_video_approved, video_label, video_score, checked_frames = await moderate_video_content_with_ai(
            save_path,
            sample_count=5,
        )
    except Exception:
        await remove_files(save_path, thumb_path)
        return redirect_with_flash(
            request,
            request.url_for("main.upload"),
            "Внутренняя ошибка модерации видео. Попробуйте позже.",
            "error",
        )

    if not is_video_approved:
        await remove_files(save_path, thumb_path)
        return redirect_with_flash(
            request,
            request.url_for("main.upload"),
            f"Видео отклонено AI-модерацией на одном из участков (проверено кадров: {checked_frames}).",
            "error",
        )

    is_approved = True
    moderation_label = video_label
    moderation_score = video_score

    if thumbnail_ok:
        try:
            is_approved, thumb_label, thumb_score = await moderate_thumbnail_with_ai(thumb_path)
        except Exception:
            await remove_files(save_path, thumb_path)
            return redirect_with_flash(
                request,
                request.url_for("main.upload"),
                "Внутренняя ошибка модерации превью. Попробуйте позже.",
                "error",
            )

        if not is_approved:
            await remove_files(save_path, thumb_path)
            return redirect_with_flash(
                request,
                request.url_for("main.upload"),
                "Видео отклонено AI-модерацией превью.",
                "error",
            )

        moderation_label = f"{video_label}+{thumb_label}"
        moderation_score = max(video_score or 0.0, thumb_score or 0.0)

    video = Video(
        user_id=user.id,
        title=title,
        description=description,
        filename=filename,
        thumbnail_filename=thumb_filename if thumbnail_ok else None,
        is_approved=is_approved,
        moderation_label=moderation_label,
        moderation_score=moderation_score,
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)

    return redirect_with_flash(
        request,
        request.url_for("main.video_detail", video_id=video.id),
        "Видео опубликовано.",
        "success",
    )


@bp.get("/video/{video_id}", name="main.video_detail")
async def video_detail(request: Request, video_id: int, session: AsyncSession = Depends(get_db_session)):
    video = await session.scalar(select(Video).options(selectinload(Video.author)).where(Video.id == video_id))
    if not video:
        raise HTTPException(status_code=404)

    video.views += 1
    await session.commit()

    user = request.state.current_user
    user_reaction = 0
    if user.is_authenticated:
        reaction = await session.scalar(
            select(VideoReaction).where(VideoReaction.user_id == user.id, VideoReaction.video_id == video.id)
        )
        user_reaction = reaction.value if reaction else 0

    comments = (
        await session.scalars(
            select(VideoComment)
            .options(selectinload(VideoComment.author))
            .where(VideoComment.video_id == video.id)
            .order_by(VideoComment.created_at.desc())
        )
    ).all()

    related_videos = await get_related_videos(video.id)
    return template_response(
        request,
        "video_detail.html",
        {
            "video": video,
            "comments": comments,
            "related_videos": related_videos,
            "user_reaction": user_reaction,
        },
    )


@bp.post("/video/{video_id}/comments", name="main.video_comment")
async def video_comment(
    request: Request,
    video_id: int,
    text: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _ensure_user(request)
    exists = await session.get(Video, video_id)
    if not exists:
        raise HTTPException(status_code=404)

    ok = await add_comment(video_id, user.id, text)
    msg = "Комментарий добавлен." if ok else "Комментарий не может быть пустым."
    return redirect_with_flash(
        request,
        request.url_for("main.video_detail", video_id=video_id),
        msg,
        "success" if ok else "error",
    )


@bp.post("/video/{video_id}/delete", name="main.video_delete")
async def video_delete(request: Request, video_id: int, session: AsyncSession = Depends(get_db_session)):
    user = await _ensure_user(request)
    video = await session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404)
    if video.user_id != user.id:
        return redirect_with_flash(
            request,
            request.url_for("main.video_detail", video_id=video.id),
            "Можно удалять только свои видео.",
            "error",
        )

    await session.execute(VideoReaction.__table__.delete().where(VideoReaction.video_id == video.id))
    files = [os.path.join(request.app.state.upload_folder, video.filename)]
    if video.thumbnail_filename:
        files.append(os.path.join(request.app.state.upload_folder, video.thumbnail_filename))

    await session.delete(video)
    await session.commit()
    await remove_files(*files)
    return redirect_with_flash(request, request.url_for("main.index"), "Видео удалено.", "success")


@bp.get("/uploads/{filename:path}", name="main.uploaded_file")
async def uploaded_file(request: Request, filename: str):
    return RedirectResponse(url=request.url_for("uploads", path=filename), status_code=307)


@bp.post("/api/videos/{video_id}/react", name="main.video_react")
async def video_react(request: Request, video_id: int, session: AsyncSession = Depends(get_db_session)):
    user = await _ensure_user(request)
    video = await session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404)

    payload = await request.json()
    action = payload.get("action")
    if action not in {"like", "dislike"}:
        return JSONResponse({"error": "invalid_action"}, status_code=400)

    likes, dislikes, user_reaction = await toggle_reaction(video.id, user.id, action)
    return JSONResponse({"likes": likes, "dislikes": dislikes, "user_reaction": user_reaction})
