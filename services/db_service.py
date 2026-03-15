from sqlalchemy import select, delete, update, func, case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from models.db_models import Account, Video, VideoHistory

ALLOWED_SORT_FIELDS = {
    "collect_rate", "engagement_rate", "create_time", "play_count",
    "digg_count", "comment_count", "collect_count", "share_count", "duration",
}


async def upsert_account(db: AsyncSession, account_data: dict) -> dict:
    stmt = insert(Account).values(**account_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sec_user_id"],
        set_={k: stmt.excluded[k] for k in account_data if k != "sec_user_id"},
    )
    stmt = stmt.returning(Account)
    result = await db.execute(stmt)
    await db.commit()
    row = result.fetchone()
    return _account_to_dict(row[0]) if row else {}


async def get_accounts(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    accounts = []
    for acc in result.scalars().all():
        d = _account_to_dict(acc)
        # 单独查询视频统计
        stats = await db.execute(
            select(
                func.count(Video.id),
                func.avg(Video.collect_rate),
                func.max(Video.collect_rate),
                func.avg(Video.engagement_rate),
                func.max(Video.engagement_rate),
            ).where(Video.account_sec_user_id == acc.sec_user_id)
        )
        row = stats.one()
        d["_synced"] = row[0] or 0
        d["_avgCollectRate"] = round(float(row[1] or 0), 6)
        d["_topCollectRate"] = round(float(row[2] or 0), 6)
        d["_avgEngagementRate"] = round(float(row[3] or 0), 6)
        d["_topEngagementRate"] = round(float(row[4] or 0), 6)
        accounts.append(d)
    return accounts


async def get_account_by_sec_user_id(db: AsyncSession, sec_user_id: str) -> dict | None:
    result = await db.execute(select(Account).where(Account.sec_user_id == sec_user_id))
    acc = result.scalars().first()
    return _account_to_dict(acc) if acc else None


async def delete_account(db: AsyncSession, sec_user_id: str) -> None:
    await db.execute(delete(Video).where(Video.account_sec_user_id == sec_user_id))
    await db.execute(delete(Account).where(Account.sec_user_id == sec_user_id))
    await db.commit()


async def upsert_videos_batch(db: AsyncSession, sec_user_id: str, videos: list[dict]) -> None:
    if not videos:
        return
    # 播放量和比率由 batch-stats 管理，同步时不覆盖
    keep_fields = {"play_count", "collect_rate", "engagement_rate"}
    for v in videos:
        v["account_sec_user_id"] = sec_user_id
    stmt = insert(Video).values(videos)
    update_cols = {
        k: stmt.excluded[k]
        for k in videos[0]
        if k != "aweme_id" and k not in keep_fields
    }
    stmt = stmt.on_conflict_do_update(index_elements=["aweme_id"], set_=update_cols)
    await db.execute(stmt)
    await db.commit()


async def get_account_videos(
    db: AsyncSession, sec_user_id: str, sort_by: str = "create_time", order: str = "desc"
) -> list[dict]:
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "create_time"
    col = getattr(Video, sort_by, Video.create_time)
    order_col = col.desc() if order == "desc" else col.asc()
    result = await db.execute(
        select(Video).where(Video.account_sec_user_id == sec_user_id).order_by(order_col)
    )
    return [_video_to_dict(row) for row in result.scalars().all()]


async def update_video_stats(db: AsyncSession, aweme_id: str, stats: dict) -> None:
    await db.execute(update(Video).where(Video.aweme_id == aweme_id).values(**stats))
    await db.commit()


async def batch_update_video_stats(db: AsyncSession, stats: dict[str, dict]) -> None:
    for aweme_id, s in stats.items():
        await db.execute(update(Video).where(Video.aweme_id == aweme_id).values(**s))
    await db.commit()


async def batch_update_play_count(db: AsyncSession, play_updates: dict[str, int]) -> None:
    """只更新播放量，collect_rate 和 engagement_rate 用数据库现有数据计算"""
    from sqlalchemy import case, cast, Float
    for aweme_id, play_count in play_updates.items():
        await db.execute(
            update(Video)
            .where(Video.aweme_id == aweme_id)
            .values(
                play_count=play_count,
                collect_rate=cast(Video.collect_count, Float) / play_count,
                engagement_rate=cast(
                    Video.digg_count + Video.comment_count + Video.share_count + Video.collect_count, Float
                ) / play_count,
            )
        )
    await db.commit()


async def save_video_history(db: AsyncSession, video_data: dict) -> dict:
    aweme_id = video_data.get("aweme_id", "")
    entry = VideoHistory(aweme_id=aweme_id, data=video_data)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _history_to_dict(entry)


async def get_video_history(db: AsyncSession, limit: int = 50) -> list[dict]:
    result = await db.execute(
        select(VideoHistory).order_by(VideoHistory.created_at.desc()).limit(limit)
    )
    return [_history_to_dict(row) for row in result.scalars().all()]


async def clear_video_history(db: AsyncSession) -> None:
    await db.execute(delete(VideoHistory))
    await db.commit()


# ---- helpers ----

def _account_to_dict(obj: Account) -> dict:
    return {
        "id": obj.id,
        "account_id": obj.account_id,
        "sec_user_id": obj.sec_user_id,
        "unique_id": obj.unique_id,
        "nickname": obj.nickname,
        "avatar_url": obj.avatar_url,
        "follower_count": obj.follower_count,
        "following_count": obj.following_count,
        "total_favorited": obj.total_favorited,
        "video_count": obj.video_count,
        "signature": obj.signature,
        "is_own_account": obj.is_own_account,
        "category": obj.category,
        "last_synced_at": obj.last_synced_at,
        "notes": obj.notes,
        "created_at": str(obj.created_at) if obj.created_at else "",
        "updated_at": str(obj.updated_at) if obj.updated_at else "",
    }


def _video_to_dict(obj: Video) -> dict:
    return {
        "id": obj.id,
        "aweme_id": obj.aweme_id,
        "account_sec_user_id": obj.account_sec_user_id,
        "account_id": obj.account_id,
        "desc": obj.desc,
        "create_time": obj.create_time,
        "duration": obj.duration,
        "play_count": obj.play_count,
        "digg_count": obj.digg_count,
        "comment_count": obj.comment_count,
        "collect_count": obj.collect_count,
        "share_count": obj.share_count,
        "collect_rate": obj.collect_rate,
        "engagement_rate": obj.engagement_rate,
        "tags": obj.tags,
        "music_title": obj.music_title,
        "video_url": obj.video_url,
        "cover_url": obj.cover_url,
        "is_co_creation": obj.is_co_creation,
        "co_creation_users": obj.co_creation_users,
        "source_url": obj.source_url,
        "author_nickname": obj.author_nickname,
        "author_avatar": obj.author_avatar,
        "author_unique_id": obj.author_unique_id,
        "author_follower_count": obj.author_follower_count,
        "created_at": str(obj.created_at) if obj.created_at else "",
        "updated_at": str(obj.updated_at) if obj.updated_at else "",
    }


def _history_to_dict(obj: VideoHistory) -> dict:
    return {
        "id": obj.id,
        "aweme_id": obj.aweme_id,
        "data": obj.data,
        "created_at": str(obj.created_at) if obj.created_at else "",
        "updated_at": str(obj.updated_at) if obj.updated_at else "",
    }
