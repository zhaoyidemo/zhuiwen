from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, Text, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(128), default="")
    sec_user_id: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    unique_id: Mapped[str] = mapped_column(String(128), default="")
    nickname: Mapped[str] = mapped_column(String(256), default="")
    avatar_url: Mapped[str] = mapped_column(Text, default="")
    follower_count: Mapped[int] = mapped_column(BigInteger, default=0)
    following_count: Mapped[int] = mapped_column(BigInteger, default=0)
    total_favorited: Mapped[int] = mapped_column(BigInteger, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    signature: Mapped[str] = mapped_column(Text, default="")
    is_own_account: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(64), default="竞品")
    last_synced_at: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_accounts_account_id", "account_id"),
        Index("ix_accounts_sec_user_id", "sec_user_id", unique=True),
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aweme_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    account_sec_user_id: Mapped[str] = mapped_column(String(256), default="")
    account_id: Mapped[str] = mapped_column(String(128), default="")
    desc: Mapped[str] = mapped_column(Text, default="")
    create_time: Mapped[str] = mapped_column(String(64), default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    play_count: Mapped[int] = mapped_column(BigInteger, default=0)
    digg_count: Mapped[int] = mapped_column(BigInteger, default=0)
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0)
    collect_count: Mapped[int] = mapped_column(BigInteger, default=0)
    share_count: Mapped[int] = mapped_column(BigInteger, default=0)
    collect_rate: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[str] = mapped_column(Text, default="")
    video_tags: Mapped[str] = mapped_column(Text, default="")
    music_title: Mapped[str] = mapped_column(String(512), default="")
    video_url: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")
    is_co_creation: Mapped[bool] = mapped_column(Boolean, default=False)
    co_creation_users: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    author_nickname: Mapped[str] = mapped_column(String(256), default="")
    author_avatar: Mapped[str] = mapped_column(Text, default="")
    author_unique_id: Mapped[str] = mapped_column(String(128), default="")
    author_follower_count: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_videos_aweme_id", "aweme_id", unique=True),
        Index("ix_videos_account_sec_user_id", "account_sec_user_id"),
    )


class VideoFavorite(Base):
    __tablename__ = "video_favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aweme_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_video_favorites_aweme_id", "aweme_id", unique=True),
    )


class VideoHistory(Base):
    __tablename__ = "video_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aweme_id: Mapped[str] = mapped_column(String(128), default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_video_history_aweme_id", "aweme_id"),
    )
