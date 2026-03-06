from __future__ import annotations

from sqlalchemy import or_

from models import Subscription, Video, VideoComment, VideoReaction, db


def get_home_feed(search: str | None, only_subscriptions: bool, viewer_id: int | None):
    query = Video.query.filter_by(is_approved=True)

    if search:
        query = query.filter(
            or_(
                Video.title.ilike(f"%{search}%"),
                Video.description.ilike(f"%{search}%"),
            )
        )

    if only_subscriptions and viewer_id:
        followed_ids = (
            db.session.query(Subscription.followed_id)
            .filter(Subscription.follower_id == viewer_id)
            .subquery()
        )
        query = query.filter(Video.user_id.in_(followed_ids))

    return query.order_by(Video.created_at.desc()).all()


def toggle_reaction(video: Video, user_id: int, action: str) -> tuple[int, int, int]:
    value = 1 if action == "like" else -1

    reaction = VideoReaction.query.filter_by(user_id=user_id, video_id=video.id).first()
    user_reaction_value = 0

    if reaction and reaction.value == value:
        db.session.delete(reaction)
    else:
        if reaction:
            reaction.value = value
        else:
            db.session.add(VideoReaction(user_id=user_id, video_id=video.id, value=value))
        user_reaction_value = value

    db.session.commit()

    likes_count = VideoReaction.query.filter_by(video_id=video.id, value=1).count()
    dislikes_count = VideoReaction.query.filter_by(video_id=video.id, value=-1).count()
    video.likes = likes_count
    video.dislikes = dislikes_count
    db.session.commit()

    return likes_count, dislikes_count, user_reaction_value


def add_comment(video_id: int, user_id: int, text: str) -> bool:
    clean_text = text.strip()
    if not clean_text:
        return False

    comment = VideoComment(video_id=video_id, user_id=user_id, text=clean_text)
    db.session.add(comment)
    db.session.commit()
    return True


def get_related_videos(video_id: int, limit: int = 8):
    return (
        Video.query.filter(Video.id != video_id, Video.is_approved.is_(True))
        .order_by(Video.created_at.desc())
        .limit(limit)
        .all()
    )
