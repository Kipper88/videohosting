from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    bio = db.Column(db.String(500), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    videos = db.relationship("Video", back_populates="author", lazy="dynamic")
    subscribers = db.relationship(
        "Subscription",
        foreign_keys="Subscription.followed_id",
        back_populates="followed",
        lazy="dynamic",
    )
    subscriptions = db.relationship(
        "Subscription",
        foreign_keys="Subscription.follower_id",
        back_populates="follower",
        lazy="dynamic",
    )


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    thumbnail_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    likes = db.Column(db.Integer, default=0, nullable=False)
    dislikes = db.Column(db.Integer, default=0, nullable=False)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    moderation_label = db.Column(db.String(64), nullable=True)
    moderation_score = db.Column(db.Float, nullable=True)

    author = db.relationship("User", back_populates="videos")
    reactions = db.relationship("VideoReaction", back_populates="video", lazy="dynamic")


class VideoReaction(db.Model):
    """
    Лайки/дизлайки к видео.
    value: +1 — лайк, -1 — дизлайк.
    """

    __tablename__ = "video_reactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # 1 или -1
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
    video = db.relationship("Video", back_populates="reactions")

    __table_args__ = (
        db.UniqueConstraint("user_id", "video_id", name="uix_user_video_reaction"),
    )


class Subscription(db.Model):
    """
    Подписки на авторов.
    follower_id подписан на followed_id.
    """

    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    follower = db.relationship("User", foreign_keys=[follower_id], back_populates="subscriptions")
    followed = db.relationship("User", foreign_keys=[followed_id], back_populates="subscribers")

    __table_args__ = (
        db.UniqueConstraint("follower_id", "followed_id", name="uix_follower_followed"),
    )


def init_db(app) -> None:
    """Создать таблицы БД."""
    with app.app_context():
        db.create_all()

