# 继续追问 — 项目指南

## 快速了解系统状态

```bash
# 系统全景自检（数据库、数据量、外部服务、最近任务）
curl -s https://jixuzhuiwen.com/api/diagnostics -H "X-Site-Password: $PASSWORD"

# API 自动化测试（核心端点 pass/fail）
curl -s https://jixuzhuiwen.com/api/self-test -H "X-Site-Password: $PASSWORD"

# API 完整文档
# https://jixuzhuiwen.com/openapi.json
# https://jixuzhuiwen.com/docs
```

## 项目架构

- **线上地址**：https://jixuzhuiwen.com
- **仓库**：D:\claude-workspace\zhuiwen（GitHub: zhaoyidemo/zhuiwen）
- **部署**：Railway（Dockerfile），Cloudflare 代理
- **技术栈**：FastAPI + PostgreSQL + Anthropic Claude + TikHub + Alpine.js

## 代码结构

```
zhuiwen/
├── main.py                    # FastAPI 主程序，中间件，全局端点
├── config.py                  # 环境变量配置
├── database.py                # 数据库连接和迁移
├── models/
│   ├── db_models.py           # SQLAlchemy 模型（8张表）
│   ├── schemas.py             # Pydantic 模型（TikHub 数据）
│   └── api_models.py          # API 统一请求/响应模型
├── routers/
│   ├── video.py               # /api/videos — 视频分析
│   ├── account.py             # /api/accounts — 竞品雷达
│   ├── favorite.py            # /api/favorites — 爆款收藏
│   ├── prompts.py             # /api/prompts — 提示词管理
│   ├── guest.py               # /api/guests — 嘉宾研究（最大的路由）
│   └── analysis.py            # /api/analysis — 飞书批量分析
├── services/
│   ├── ai_service.py          # Claude API 调用 + 全部 AI 提示词
│   ├── db_service.py          # 数据库 CRUD
│   ├── tikhub_service.py      # TikHub（抖音数据）API
│   ├── feishu_service.py      # 飞书多维表 API
│   ├── web_fetcher.py         # 网页抓取 + 微信公众号处理
│   ├── video_processor.py     # ffmpeg 截帧
│   └── task_service.py        # 后台任务状态管理
├── static/
│   └── index.html             # 前端 SPA（Alpine.js + Tailwind）
├── Dockerfile                 # Railway 部署用
└── requirements.txt
```

## API 规范

- 统一响应格式：`{code: 0, data: {...}, message: ""}`
- 认证：Header `X-Site-Password`（密码在 Railway 环境变量中，代码默认值已失效）
- 后台任务返回 `task_id`，通过 `GET /api/tasks/{task_id}` 查询进度
- 所有端点有 summary + description，AI 可读 /openapi.json 自发现

## 嘉宾研究 AI 同事

| AI 同事 | 提示词名 | 模型 |
|---------|---------|------|
| AI调查员 | AI调查员 | Sonnet + web search |
| AI策划专员 | AI策划专员 | Sonnet |
| AI内容编导 | AI内容编导 | Opus |
| AI切片编导 | AI切片编导 | Opus |
| AI热点编导 | AI热点编导 | Sonnet + web search |
| AI嘉宾替身 | AI嘉宾替身 | Sonnet |

提示词全部在 `ai_service.py` 的 `DEFAULT_PROMPTS` 字典中，可通过提示词管理界面自定义。

## 模型版本

- Opus: `claude-opus-4-6`
- Sonnet: `claude-sonnet-4-6`

## 注意事项

- 密码已从 Railway 环境变量覆盖，代码中的默认值已失效
- 提示词管理已独立为 `/api/prompts`（不再挂在 favorites 下）
- 视频有 status 字段（active/deleted），已删除视频在汇总指标中排除
- 素材有 status 字段（pending/verified/unverified/failed/excluded）
- 所有后台任务返回 task_id，前端用 pollTask() 轮询
