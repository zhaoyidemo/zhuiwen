from pydantic import BaseModel
from typing import Optional


class VideoParseRequest(BaseModel):
    url: str


class VideoData(BaseModel):
    aweme_id: str = ""
    account_id: str = ""
    desc: str = ""
    create_time: str = ""
    duration: int = 0
    play_count: int = 0
    digg_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    share_count: int = 0
    collect_rate: float = 0.0
    tags: str = ""
    music_title: str = ""
    video_url: str = ""
    cover_url: str = ""
    is_co_creation: bool = False
    co_creation_users: str = ""
    source_url: str = ""
    author_nickname: str = ""
    author_avatar: str = ""
    author_unique_id: str = ""
    author_follower_count: int = 0


class AccountAddRequest(BaseModel):
    unique_id: str
    category: str = "竞品"


class AccountData(BaseModel):
    account_id: str = ""
    sec_user_id: str = ""
    unique_id: str = ""
    nickname: str = ""
    avatar_url: str = ""
    follower_count: int = 0
    following_count: int = 0
    total_favorited: int = 0
    video_count: int = 0
    signature: str = ""
    is_own_account: bool = False
    category: str = "竞品"
    last_synced_at: str = ""
    notes: str = ""


class AnalysisRequest(BaseModel):
    video_ids: list[str] = []
    analysis_type: str = "爆款分析"
    custom_prompt: Optional[str] = None


class AnalysisResult(BaseModel):
    analysis_id: str = ""
    analysis_type: str = ""
    input_description: str = ""
    result: str = ""
    created_at: str = ""


class PasswordRequest(BaseModel):
    password: str
