from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from models import SessionLocal, Subscription, User, Video, VideoComment, VideoReaction


async def get_home_feed(search: str | None, only_subscriptions: bool, viewer_id: int | None):
    async with SessionLocal() as session:
        query = select(Video).options(selectinload(Video.author)).where(Video.is_approved.is_(True))

        if search:
            normalized = search.strip().lower()
            query = query.join(User, Video.user_id == User.id, isouter=True).where(
                or_(
                    func.lower(Video.title).contains(normalized),
                    func.lower(func.coalesce(Video.description, "")).contains(normalized),
                    func.lower(func.coalesce(User.username, "")).contains(normalized),
                )
            )

        if only_subscriptions and viewer_id:
            followed_ids = select(Subscription.followed_id).where(Subscription.follower_id == viewer_id)
            query = query.where(Video.user_id.in_(followed_ids))

        result = await session.scalars(query.order_by(Video.created_at.desc()))
        return result.all()


async def toggle_reaction(video_id: int, user_id: int, action: str) -> tuple[int, int, int]:
    value = 1 if action == "like" else -1

    async with SessionLocal() as session:
        reaction = await session.scalar(
            select(VideoReaction).where(VideoReaction.user_id == user_id, VideoReaction.video_id == video_id)
        )
        user_reaction_value = 0

        if reaction and reaction.value == value:
            await session.delete(reaction)
        else:
            if reaction:
                reaction.value = value
            else:
                session.add(VideoReaction(user_id=user_id, video_id=video_id, value=value))
            user_reaction_value = value

        likes_count = await session.scalar(
            select(func.count(VideoReaction.id)).where(VideoReaction.video_id == video_id, VideoReaction.value == 1)
        )
        dislikes_count = await session.scalar(
            select(func.count(VideoReaction.id)).where(VideoReaction.video_id == video_id, VideoReaction.value == -1)
        )

        video = await session.get(Video, video_id)
        if video:
            video.likes = int(likes_count or 0)
            video.dislikes = int(dislikes_count or 0)

        await session.commit()
        return int(likes_count or 0), int(dislikes_count or 0), user_reaction_value


async def add_comment(video_id: int, user_id: int, text: str) -> bool:
    clean_text = text.strip()
    if not clean_text:
        return False

    async with SessionLocal() as session:
        session.add(VideoComment(video_id=video_id, user_id=user_id, text=clean_text))
        await session.commit()
    return True


async def get_related_videos(video_id: int, limit: int = 8):
    async with SessionLocal() as session:
        result = await session.scalars(
            select(Video)
            .options(selectinload(Video.author))
            .where(Video.id != video_id, Video.is_approved.is_(True))
            .order_by(Video.created_at.desc())
            .limit(limit)
        )
        return result.all()
