import time
import asyncio
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://open.feishu.cn/open-apis"

_token_cache = {"token": "", "expires_at": 0}


async def get_tenant_access_token() -> str:
    """获取飞书 tenant_access_token，带缓存"""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.FEISHU_APP_ID,
                "app_secret": settings.FEISHU_APP_SECRET,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 0:
        raise Exception(f"获取飞书 token 失败: {data.get('msg')}")

    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expires_at"] = now + data.get("expire", 7200)
    return _token_cache["token"]


async def _request(method: str, path: str, json_data: dict = None, params: dict = None) -> dict:
    token = await get_tenant_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    app_token = settings.FEISHU_BITABLE_APP_TOKEN

    url = f"{BASE_URL}{path}".replace("{app_token}", app_token)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, url, headers=headers, json=json_data, params=params)
        resp.raise_for_status()
        return resp.json()


async def create_record(table_id: str, fields: dict) -> dict:
    """创建单条记录"""
    data = await _request(
        "POST",
        f"/bitable/v1/apps/{{app_token}}/tables/{table_id}/records",
        json_data={"fields": fields},
    )
    if data.get("code") != 0:
        logger.error(f"创建记录失败: {data.get('msg')}")
    return data


async def batch_create_records(table_id: str, records: list[dict]) -> list[dict]:
    """批量创建记录，自动分批 + 节流"""
    results = []
    batch_size = 450  # 飞书限制 500，留余量

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        data = await _request(
            "POST",
            f"/bitable/v1/apps/{{app_token}}/tables/{table_id}/records/batch_create",
            json_data={"records": [{"fields": r} for r in batch]},
        )
        if data.get("code") != 0:
            logger.error(f"批量创建记录失败 (batch {i}): {data.get('msg')}")
        results.append(data)

        if i + batch_size < len(records):
            await asyncio.sleep(1)  # 节流

    return results


async def search_records(table_id: str, filter_expr: Optional[str] = None, page_size: int = 100) -> list[dict]:
    """查询记录"""
    body = {"page_size": page_size}
    if filter_expr:
        body["filter"] = filter_expr

    data = await _request(
        "POST",
        f"/bitable/v1/apps/{{app_token}}/tables/{table_id}/records/search",
        json_data=body,
    )

    if data.get("code") != 0:
        logger.warning(f"查询记录失败: {data.get('msg')}, 尝试用 list 接口")
        # fallback 到 list 接口
        params = {"page_size": page_size}
        data = await _request(
            "GET",
            f"/bitable/v1/apps/{{app_token}}/tables/{table_id}/records",
            params=params,
        )

    items = data.get("data", {}).get("items", []) or []
    return items


async def update_record(table_id: str, record_id: str, fields: dict) -> dict:
    """更新记录"""
    data = await _request(
        "PUT",
        f"/bitable/v1/apps/{{app_token}}/tables/{table_id}/records/{record_id}",
        json_data={"fields": fields},
    )
    return data


def _video_to_feishu_fields(video) -> dict:
    """将 VideoData 转为飞书字段格式"""
    fields = {
        "aweme_id": str(video.aweme_id),
        "account_id": str(video.account_id),
        "desc": video.desc or "",
        "duration": video.duration or 0,
        "play_count": video.play_count or 0,
        "digg_count": video.digg_count or 0,
        "comment_count": video.comment_count or 0,
        "collect_count": video.collect_count or 0,
        "share_count": video.share_count or 0,
        "collect_rate": round(video.collect_rate * 100, 4),  # 存为百分比数字
        "tags": video.tags or "",
        "music_title": video.music_title or "",
        "is_co_creation": video.is_co_creation,
        "co_creation_users": video.co_creation_users or "",
    }

    # 日期字段：毫秒时间戳
    if video.create_time:
        try:
            from datetime import datetime
            dt = datetime.strptime(video.create_time, "%Y-%m-%d %H:%M:%S")
            fields["create_time"] = int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            pass

    # 当前时间作为同步时间
    import time
    fields["synced_at"] = int(time.time() * 1000)

    # 超链接字段
    if video.video_url:
        fields["video_url"] = {"text": "视频链接", "link": video.video_url}
    if video.cover_url:
        fields["cover_url"] = {"text": "封面", "link": video.cover_url}
    if video.source_url:
        fields["source_url"] = {"text": "原始链接", "link": video.source_url}

    return fields


def _account_to_feishu_fields(account, category: str = "竞品") -> dict:
    """将 AccountData 转为飞书字段格式"""
    import time
    fields = {
        "account_id": str(account.account_id),
        "unique_id": account.unique_id or "",
        "nickname": account.nickname or "",
        "follower_count": account.follower_count or 0,
        "following_count": account.following_count or 0,
        "total_favorited": account.total_favorited or 0,
        "video_count": account.video_count or 0,
        "signature": account.signature or "",
        "is_own_account": category in ("自己主号", "矩阵号"),
        "category": category,
        "last_synced_at": int(time.time() * 1000),
        "notes": "",
    }
    if account.avatar_url:
        fields["avatar_url"] = {"text": "头像", "link": account.avatar_url}
    return fields


async def save_video(video, table_id: str = None) -> dict:
    """保存视频数据到飞书"""
    tid = table_id or settings.FEISHU_TABLE_VIDEOS
    if not tid:
        logger.warning("FEISHU_TABLE_VIDEOS 未配置，跳过飞书写入")
        return {"skipped": True}
    fields = _video_to_feishu_fields(video)
    return await create_record(tid, fields)


async def save_videos_batch(videos: list, table_id: str = None) -> list:
    """批量保存视频数据"""
    tid = table_id or settings.FEISHU_TABLE_VIDEOS
    if not tid:
        logger.warning("FEISHU_TABLE_VIDEOS 未配置，跳过飞书写入")
        return [{"skipped": True}]
    records = [_video_to_feishu_fields(v) for v in videos]
    return await batch_create_records(tid, records)


async def save_account(account, category: str = "竞品", table_id: str = None) -> dict:
    """保存账号数据到飞书"""
    tid = table_id or settings.FEISHU_TABLE_ACCOUNTS
    if not tid:
        logger.warning("FEISHU_TABLE_ACCOUNTS 未配置，跳过飞书写入")
        return {"skipped": True}
    fields = _account_to_feishu_fields(account, category)
    return await create_record(tid, fields)


async def get_accounts(table_id: str = None) -> list[dict]:
    """获取所有已添加的账号"""
    tid = table_id or settings.FEISHU_TABLE_ACCOUNTS
    if not tid:
        return []
    items = await search_records(tid)
    return [item.get("fields", {}) for item in items]


async def get_account_videos(account_id: str, table_id: str = None) -> list[dict]:
    """获取指定账号的所有视频"""
    tid = table_id or settings.FEISHU_TABLE_VIDEOS
    if not tid:
        return []
    filter_expr = f'CurrentValue.[account_id] = "{account_id}"'
    items = await search_records(tid, filter_expr)
    return [item.get("fields", {}) for item in items]
