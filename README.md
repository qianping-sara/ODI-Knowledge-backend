# ODI-Knowledge-backend

FastAPI 后端，提供 ODI 企业知识库问答 API，支持流式输出与工具调用过程展示。

## 环境

- Python 3.11+
- 复制 `.env.example` 为 `.env` 并填写配置（数据库、Azure OpenAI、PageIndex 等）

## 启动命令

```bash
# 安装依赖
uv sync

# 数据库迁移
uv run alembic upgrade head

# 开发启动（热重载）
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 或使用脚本
./run-backend.sh

# Docker
docker build -t odi-knowledge-backend .
docker run -p 8000:8000 --env-file .env odi-knowledge-backend
```

## API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/sessions` | 创建会话 |
| GET | `/api/v1/sessions` | 会话列表 |
| GET | `/api/v1/sessions/{session_id}` | 获取单个会话 |
| PUT | `/api/v1/sessions/{session_id}` | 重命名会话 |
| PUT | `/api/v1/sessions/{session_id}/status` | 更新会话状态 |
| DELETE | `/api/v1/sessions` | 删除会话 |
| GET | `/api/v1/sessions/{session_id}/messages` | 消息列表 |
| POST | `/api/v1/completions` | 聊天补全（流式/非流式） |

详细接口说明见 `docs/API_SPEC.md`。
