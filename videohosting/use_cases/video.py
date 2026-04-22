from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from videohosting.db import (
    CommentReaction,
    SessionLocal,
    Subscription,
    User,
    Video,
    VideoComment,
    VideoReaction,
    ViewHistory,
)


def _split_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    return [tag.strip().lower() for tag in tags.split(",") if tag.strip()]


async def get_home_feed(search: str | None, only_subscriptions: bool, viewer_id: int | None):
    async with SessionLocal() as session:
        base_filters = [Video.is_deleted.is_(False), Video.moderation_status == "approved", Video.is_short.is_(False)]
        query = select(Video).options(selectinload(Video.author)).where(*base_filters)

        if search:
            normalized = search.strip().lower()
            query = query.join(User, Video.user_id == User.id, isouter=True).where(
                or_(
                    func.lower(Video.title).contains(normalized),
                    func.lower(func.coalesce(Video.description, "")).contains(normalized),
                    func.lower(func.coalesce(User.username, "")).contains(normalized),
                    func.lower(func.coalesce(Video.tags, "")).contains(normalized),
                )
            )

        if only_subscriptions and viewer_id:
            followed_ids = select(Subscription.followed_id).where(Subscription.follower_id == viewer_id)
            query = query.where(Video.user_id.in_(followed_ids))
            result = await session.scalars(query.order_by(Video.created_at.desc()))
            return result.all()

        if viewer_id:
            top_tags = await _get_top_viewer_tags(session, viewer_id)
            if top_tags:
                tag_filters = [func.lower(func.coalesce(Video.tags, "")).contains(tag) for tag in top_tags]
                query = query.where(or_(*tag_filters))

        day_ago = datetime.utcnow() - timedelta(hours=24)
        popularity_score = (Video.views * 0.3) + (Video.likes * 1.7)
        result = await session.scalars(query.where(Video.created_at >= day_ago).order_by(popularity_score.desc(), Video.created_at.desc()))
        items = result.all()

        if len(items) < 24:
            fallback = await session.scalars(
                select(Video)
                .options(selectinload(Video.author))
                .where(*base_filters)
                .order_by(Video.created_at.desc())
                .limit(24)
            )
            fallback_items = fallback.all()
            existing = {video.id for video in items}
            items.extend([video for video in fallback_items if video.id not in existing])

        return items


async def _get_top_viewer_tags(session, viewer_id: int, limit: int = 3) -> list[str]:
    history = (
        await session.scalars(
            select(Video.tags)
            .join(ViewHistory, ViewHistory.video_id == Video.id)
            .where(ViewHistory.user_id == viewer_id)
            .order_by(ViewHistory.last_viewed_at.desc())
            .limit(100)
        )
    ).all()
    counter = Counter()
    for tag_blob in history:
        counter.update(_split_tags(tag_blob))
    return [tag for tag, _ in counter.most_common(limit)]


async def get_shorts_feed(offset: int = 0, limit: int = 12):
    async with SessionLocal() as session:
        result = await session.scalars(
            select(Video)
            .options(selectinload(Video.author))
            .where(
                Video.is_deleted.is_(False),
                Video.moderation_status == "approved",
                Video.is_short.is_(True),
            )
            .order_by(Video.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
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


async def add_comment(video_id: int, user_id: int, text: str, parent_id: int | None = None) -> bool:
    clean_text = text.strip()
    if not clean_text:
        return False

    async with SessionLocal() as session:
        if parent_id:
            parent = await session.get(VideoComment, parent_id)
            if not parent or parent.video_id != video_id:
                return False
        session.add(VideoComment(video_id=video_id, user_id=user_id, text=clean_text, parent_id=parent_id))
        await session.commit()
    return True


async def toggle_comment_reaction(comment_id: int, user_id: int, action: str) -> tuple[int, int, int]:
    value = 1 if action == "like" else -1
    async with SessionLocal() as session:
        reaction = await session.scalar(
            select(CommentReaction).where(CommentReaction.user_id == user_id, CommentReaction.comment_id == comment_id)
        )
        user_reaction = 0
        if reaction and reaction.value == value:
            await session.delete(reaction)
        else:
            if reaction:
                reaction.value = value
            else:
                session.add(CommentReaction(user_id=user_id, comment_id=comment_id, value=value))
            user_reaction = value

        likes = await session.scalar(
            select(func.count(CommentReaction.id)).where(CommentReaction.comment_id == comment_id, CommentReaction.value == 1)
        )
        dislikes = await session.scalar(
            select(func.count(CommentReaction.id)).where(CommentReaction.comment_id == comment_id, CommentReaction.value == -1)
        )
        comment = await session.get(VideoComment, comment_id)
        if comment:
            comment.likes = int(likes or 0)
            comment.dislikes = int(dislikes or 0)
        await session.commit()
        return int(likes or 0), int(dislikes or 0), user_reaction


async def get_comments_tree(video_id: int):
    async with SessionLocal() as session:
        comments = (
            await session.scalars(
                select(VideoComment)
                .options(selectinload(VideoComment.author))
                .where(VideoComment.video_id == video_id)
                .order_by(VideoComment.created_at.asc())
            )
        ).all()

    by_parent: dict[int | None, list[VideoComment]] = {}
    for comment in comments:
        by_parent.setdefault(comment.parent_id, []).append(comment)

    def build(parent_id: int | None):
        nodes = []
        for comment in by_parent.get(parent_id, []):
            nodes.append({"comment": comment, "children": build(comment.id)})
        return nodes

    return build(None)


async def register_view(user_id: int, video_id: int) -> None:
    async with SessionLocal() as session:
        entry = await session.scalar(
            select(ViewHistory).where(and_(ViewHistory.user_id == user_id, ViewHistory.video_id == video_id))
        )
        if entry:
            entry.last_viewed_at = datetime.utcnow()
        else:
            session.add(ViewHistory(user_id=user_id, video_id=video_id, last_viewed_at=datetime.utcnow()))
        await session.commit()


async def get_related_videos(video_id: int, tags: str | None, limit: int = 8):
    async with SessionLocal() as session:
        base = select(Video).options(selectinload(Video.author)).where(
            Video.id != video_id,
            Video.is_deleted.is_(False),
            Video.moderation_status == "approved",
        )
        for tag in _split_tags(tags)[:2]:
            base = base.where(func.lower(func.coalesce(Video.tags, "")).contains(tag))
        result = await session.scalars(base.order_by(Video.created_at.desc()).limit(limit))
        return result.all()
