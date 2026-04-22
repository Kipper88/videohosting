from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class UserRole(str, Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default=UserRole.USER.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    videos: Mapped[list[Video]] = relationship("Video", back_populates="author")
    comments: Mapped[list[VideoComment]] = relationship("VideoComment", back_populates="author")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    thumbnail_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dislikes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    deletion_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_short: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    author: Mapped[User | None] = relationship("User", back_populates="videos")
    reactions: Mapped[list[VideoReaction]] = relationship("VideoReaction", back_populates="video")
    comments: Mapped[list[VideoComment]] = relationship(
        "VideoComment", back_populates="video", cascade="all, delete-orphan"
    )


class VideoReaction(Base):
    __tablename__ = "video_reactions"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uix_user_video_reaction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    video: Mapped[Video] = relationship("Video", back_populates="reactions")


class VideoComment(Base):
    __tablename__ = "video_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("video_comments.id"), nullable=True)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dislikes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    author: Mapped[User] = relationship("User", back_populates="comments")
    video: Mapped[Video] = relationship("Video", back_populates="comments")
    parent: Mapped[VideoComment | None] = relationship("VideoComment", remote_side="VideoComment.id")


class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (UniqueConstraint("user_id", "comment_id", name="uix_user_comment_reaction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    comment_id: Mapped[int] = mapped_column(ForeignKey("video_comments.id"), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("follower_id", "followed_id", name="uix_follower_followed"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    followed_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ViewHistory(Base):
    __tablename__ = "view_history"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uix_user_video_history"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
