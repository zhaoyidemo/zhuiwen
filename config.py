import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TIKHUB_API_KEY: str = ""
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    ANTHROPIC_API_KEY: str = ""
    FEISHU_BITABLE_APP_TOKEN: str = ""
    FEISHU_TABLE_ACCOUNTS: str = ""
    FEISHU_TABLE_VIDEOS: str = ""
    FEISHU_TABLE_SNAPSHOTS: str = ""
    FEISHU_TABLE_COMMENTS: str = ""
    FEISHU_TABLE_ANALYSES: str = ""
    SITE_PASSWORD: str = "zhuiwen2024"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
