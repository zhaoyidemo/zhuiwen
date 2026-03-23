"""统一 API 请求/响应模型"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---- 统一响应 ----

class ApiResponse(BaseModel):
    """所有 API 的统一响应格式"""
    code: int = Field(0, description="状态码，0=成功，非0=失败")
    data: Any = Field(None, description="响应数据")
    message: str = Field("", description="提示信息")


class TaskResponse(BaseModel):
    """后台任务的响应"""
    code: int = 0
    data: dict = Field(default_factory=lambda: {"task_id": ""})
    message: str = ""


# ---- 认证 ----

class PasswordRequest(BaseModel):
    """密码验证请求"""
    password: str = Field(..., description="访问密码")


# ---- 视频 ----

class VideoParseRequest(BaseModel):
    """视频解析请求"""
    url: str = Field(..., description="抖音视频链接（支持短链和完整链接）")


class BatchStatsRequest(BaseModel):
    """批量视频统计请求（直接传 aweme_id 列表）"""
    # 前端直接传数组，这里用 list
    pass  # 保持向后兼容，前端直接传 list


# ---- 账号 ----

class AccountAddRequest(BaseModel):
    """添加账号请求"""
    unique_id: str = Field(..., description="抖音号（unique_id）")
    category: str = Field("竞品", description="分类：竞品/自有")


# ---- 收藏 ----

class PromptSaveRequest(BaseModel):
    """保存提示词请求"""
    name: str = Field(..., description="提示词名称")
    content: str = Field(..., description="提示词内容")


class AnalyzeRequest(BaseModel):
    """AI 分析请求"""
    prompt: Optional[str] = Field("", description="自定义提示词（留空使用默认）")
    video_data: Optional[dict] = Field(None, description="视频数据")


# ---- 嘉宾 ----

class GuestCreateRequest(BaseModel):
    """创建嘉宾请求"""
    name: str = Field(..., description="嘉宾姓名")
    description: str = Field("", description="身份描述（如：小米产品经理）")


class GuestSearchRequest(BaseModel):
    """嘉宾搜索请求"""
    extra_keywords: str = Field("", description="补充搜索词（逗号分隔，如：别名,公司名）")


class MaterialAddRequest(BaseModel):
    """手动添加素材请求"""
    url: str = Field(..., description="素材链接")
    platform: str = Field("", description="平台（抖音/B站/YouTube/小宇宙/网页）")
    title: str = Field("", description="标题（选填）")


class MaterialUpdateRequest(BaseModel):
    """编辑素材请求"""
    content: Optional[str] = Field(None, description="正文内容")
    status: Optional[str] = Field(None, description="状态（verified/unverified/excluded）")


class GuestAnalyzeRequest(BaseModel):
    """嘉宾分析请求"""
    prompt: str = Field("", description="自定义提示词（留空使用默认）")


class GuestChatRequest(BaseModel):
    """对话预演请求"""
    message: str = Field(..., description="采访问题")
    history: list[dict] = Field(default_factory=list, description="对话历史")


# ---- 辅助函数 ----

def ok(data: Any = None, message: str = "") -> dict:
    """成功响应"""
    return {"code": 0, "data": data, "message": message}


def fail(message: str, code: int = 400) -> dict:
    """失败响应"""
    return {"code": code, "data": None, "message": message}
