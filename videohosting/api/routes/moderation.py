from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from videohosting.db import Report, UserRole, Video, get_db_session
from videohosting.web.utils import redirect_with_flash, template_response

router = APIRouter(prefix="/moderation")


def _is_moderator(user) -> bool:
    return getattr(user, "is_authenticated", False) and user.role in {UserRole.MODERATOR.value, UserRole.ADMIN.value}


@router.get("", name="moderation.panel")
async def moderation_panel(request: Request, session: AsyncSession = Depends(get_db_session)):
    user = request.state.current_user
    if not _is_moderator(user):
        raise HTTPException(status_code=403)

    pending_videos = (
        await session.scalars(
            select(Video).options(selectinload(Video.author)).where(Video.moderation_status == "pending", Video.is_deleted.is_(False)).order_by(Video.created_at.asc())
        )
    ).all()
    reports = (
        await session.scalars(
            select(Report).where(Report.id.is_not(None)).order_by(Report.created_at.desc()).limit(200)
        )
    ).all()
    return template_response(request, "moderation.html", {"pending_videos": pending_videos, "reports": reports})


@router.post("/video/{video_id}/approve", name="moderation.approve")
async def approve_video(request: Request, video_id: int, session: AsyncSession = Depends(get_db_session)):
    user = request.state.current_user
    if not _is_moderator(user):
        raise HTTPException(status_code=403)
    video = await session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404)
    video.moderation_status = "approved"
    await session.commit()
    return redirect_with_flash(request, request.url_for("moderation.panel"), "Видео одобрено.", "success")


@router.post("/video/{video_id}/reject", name="moderation.reject")
async def reject_video(
    request: Request,
    video_id: int,
    deletion_reason: str = Form("Отклонено модератором"),
    session: AsyncSession = Depends(get_db_session),
):
    user = request.state.current_user
    if not _is_moderator(user):
        raise HTTPException(status_code=403)
    video = await session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404)
    video.moderation_status = "rejected"
    video.is_deleted = True
    video.deletion_reason = deletion_reason.strip()[:500] or "Отклонено модератором"
    await session.commit()
    return redirect_with_flash(request, request.url_for("moderation.panel"), "Видео отклонено.", "success")
