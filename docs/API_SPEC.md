# Company Research API 接口规范

> 基于当前 `api/` 路由整理，供前端对接参考。

**Base URL**: `/api/v1`  
**通用响应格式**: `{"code": 200 | 其他, "message"?: string, "data"?: any}`  
**错误**: `code !== 200` 或 HTTP 4xx/5xx，`message` 含错误信息。

---

## 1. 健康检查

### `GET /health`

| 项目   | 说明     |
|--------|----------|
| 描述   | 健康检查 |
| 参数   | 无       |
| 响应   | `{"status": "ok"}` |

---

## 2. Sessions 会话管理

### 2.1 创建会话

**`POST /api/v1/sessions`**

| 项目   | 说明                           |
|--------|--------------------------------|
| 描述   | 创建新的聊天会话               |
| Body   | `ChatSessionCreate` (JSON)     |
| 成功   | 200，`data` 为会话详情（含 messages 列表） |

**Request Body (ChatSessionCreate)**

```json
{
  "name": "可选，会话名称，max 255 字符，默认 New Chat"
}
```

可为空对象 `{}`，全部使用默认值。

**Response `data` 结构**

```json
{
  "id": "uuid",
  "chat_id": "uuid",
  "name": "New Chat",
  "status": "open",
  "user_id": null,
  "user_name": null,
  "user_mail": null,
  "user_data": null,
  "created_at": "2025-01-15T12:00:00.000000",
  "create_time": 1736935200000,
  "update_time": 1736935200000,
  "create_date": "Tue, 15 Jan 2025 12:00:00 GMT",
  "update_date": "Tue, 15 Jan 2025 12:00:00 GMT",
  "messages": []
}
```

---

### 2.2 会话列表

**`GET /api/v1/sessions`**

| 项目   | 说明                         |
|--------|------------------------------|
| 描述   | 分页列出会话，可过滤         |
| Query  | 见下表                       |
| 成功   | 200，`data` 为会话数组       |

**Query 参数**

| 参数       | 类型   | 默认      | 说明                         |
|------------|--------|-----------|------------------------------|
| page       | int    | 1         | 页码，≥1                     |
| page_size  | int    | 30        | 每页条数，1–100              |
| orderby    | string | updated_at| 排序字段：`updated_at` / `created_at` |
| desc       | bool   | true      | 是否降序                     |
| name       | string | -         | 按名称过滤（可选）           |
| id         | string | -         | 按会话 ID 过滤（可选）       |

**Response**

```json
{
  "code": 200,
  "data": [
    {
      "id": "uuid",
      "chat_id": "uuid",
      "name": "会话名",
      "status": "open",
      "messages": [/* message 数组 */],
      "created_at": "...",
      "create_time": 1736935200000,
      "update_time": 1736935200000,
      ...
    }
  ]
}
```

---

### 2.3 获取单个会话

**`GET /api/v1/sessions/{session_id}`**

| 项目   | 说明                           |
|--------|--------------------------------|
| 描述   | 获取指定会话详情及消息历史     |
| 路径   | `session_id` (uuid)            |
| 成功   | 200，`data` 为会话详情         |
| 失败   | 404，`Session not found`       |

---

### 2.4 重命名会话

**`PUT /api/v1/sessions/{session_id}`**

| 项目   | 说明           |
|--------|----------------|
| 描述   | 重命名会话     |
| Body   | `{"name": "新名称"}` |
| 成功   | 200            |
| 失败   | 404            |

---

### 2.5 更新会话状态

**`PUT /api/v1/sessions/{session_id}/status`**

| 项目   | 说明           |
|--------|----------------|
| 描述   | 更新会话状态   |
| Body   | `{"status": "open" | 其他}` |
| 成功   | 200            |
| 失败   | 400 / 404      |

---

### 2.6 删除会话

**`DELETE /api/v1/sessions`**

| 项目   | 说明                 |
|--------|----------------------|
| 描述   | 批量删除会话         |
| Body   | `{"ids": ["uuid1", "uuid2", ...]}` |
| 成功   | 200                  |
| 失败   | 400 (`ids` 为空) / 404 |

---

## 3. Messages 消息

### 3.1 获取会话消息列表

**`GET /api/v1/sessions/{session_id}/messages`**

| 项目   | 说明                     |
|--------|--------------------------|
| 描述   | 获取指定会话的全部消息   |
| 路径   | `session_id`             |
| 成功   | 200，`data` 为消息数组   |
| 失败   | 404                      |

**Response `data` 每项结构**

```json
{
  "id": "123",
  "role": "user" | "assistant",
  "content": "消息内容",
  "fileurls": [],
  "action": [],
  "created_at": 1736935200000
}
```

---

## 4. Completions 聊天补全（核心）

### 4.1 发起对话

**`POST /api/v1/completions`**

| 项目   | 说明                                     |
|--------|------------------------------------------|
| 描述   | 发送用户消息，获取 AI 回复               |
| Body   | `CompletionRequest`                      |
| 模式   | 支持流式 (`stream: true`) 与非流式 (`stream: false`) |
| 成功   | 200 + `data`（非流式）或 SSE 流（流式）  |

**Request Body (CompletionRequest)**

```json
{
  "session_id": "可选，缺失时自动创建新会话",
  "question": "用户问题文本",
  "file_urls": ["可选，附件 URL 列表"],
  "stream": true
}
```

- `question` 和 `file_urls` 至少有一个非空，否则 400：`Question cannot be empty.`
- `session_id` 若提供但不存在，返回 404

---

### 4.2 非流式响应

当 `stream: false` 时，响应为普通 JSON：

```json
{
  "code": 200,
  "data": {
    "answer": "AI 回复的完整文本",
    "fileurls": [],
    "id": "assistant_message_id",
    "answer_id": "assistant_message_id",
    "question_id": "user_message_id",
    "action": [],
    "session_id": "uuid"
  }
}
```

---

### 4.3 流式响应（SSE）

当 `stream: true` 时：

- **Content-Type**: `text/event-stream`
- **Header**: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`

**SSE 行格式**（每行一条 JSON，前端按行解析）：

```
data: {"code": 0, "data": {...}}

```

- `code`: 0 表示正常，1 表示错误（仅 error 事件）
- `data`: 事件负载，类型由 `data.type` 区分

**事件序列**：`progress` → 若干 `process`（tool_start/tool_end） → `final` 或 `error` → `end`

| 顺序 | 事件类型 | 说明 |
|------|----------|------|
| 1 | progress | 开始处理 |
| 2..N | process | 工具调用过程（每次 tool 有 tool_start + tool_end，可多次） |
| N+1 | final | 成功完成，携带完整 answer |
| N+1 | error | 失败，携带错误信息 |
| 最后 | end | 流结束，`data === true` |

---

### 4.4 流式事件明细（真实格式）

以下为前端会收到的**真实 JSON 结构**，直接按 `data` 解析即可。

#### progress

```json
{
  "code": 0,
  "data": {
    "type": "progress",
    "phase": "analysis",
    "status": "running",
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "ts": "2025-03-08T06:15:18.874000+00:00"
  }
}
```

#### process (tool_start)

工具开始调用时发送。`input` 为工具参数，不同工具字段不同。

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_start",
    "tool_name": "list_pageindex_documents",
    "tool_call_id": "call_8VDPdRs9Yo4xxtdb2GlXXX",
    "input": {},
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "ts": "2025-03-08T06:15:28.069000+00:00"
  }
}
```

`query_pageindex` 的 input 示例（完整事件，外层 `code` + `data`）：

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_start",
    "tool_name": "query_pageindex",
    "tool_call_id": "call_4RZ4GdHnIylgvN163gnXXX",
    "input": {
      "query": "有哪些中国企业在泰国设厂的具体案例？请确保回答包含知识来源说明（文件名及页码）。",
      "doc_ids": ["pi-cmmhbhmfd01p8faqnsw3ghlcc"]
    },
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "ts": "2025-03-08T06:15:28.070000+00:00"
  }
}
```

`think_tool` 的 input 示例：

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_start",
    "tool_name": "think_tool",
    "tool_call_id": "call_N6gioYP8YWg5BeHdSZLXXX",
    "input": {
      "reflection": "已找到明确的泰国设厂案例，均来自..."
    },
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "ts": "2025-03-08T06:15:28.071000+00:00"
  }
}
```

#### process (tool_end)

工具返回时发送。**必须**与对应 `tool_start` 的 `tool_call_id` 一致，用于前端配对更新同一张卡片。

**成功（status: completed）**：

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_end",
    "tool_name": "list_pageindex_documents",
    "tool_call_id": "call_8VDPdRs9Yo4xxtdb2GlXXX",
    "status": "completed",
    "output_preview": "Available PageIndex Knowledge Base Documents (id | name | description):\n\n**pi-cmmhbhu7601pafaqnqxypm18h**: Guide直接投资和间接投…",
    "output_raw": "Available PageIndex Knowledge Base Documents (id | name | description):\n\n**pi-cmmhbhu7601pafaqnqxypm18h**: Guide直接投资和间接投资...\n\n（完整文本，可折叠展示）",
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "ts": "2025-03-08T06:15:28.071000+00:00"
  }
}
```

- `output_preview`: 前 200 字符摘要
- `output_raw`: 工具完整返回文本
- `output_json`: 当前实现为 `null`，后续 Phase 2 可解析 PageIndex 等结构化返回

**失败（status: error）**：当工具内部捕获异常并返回错误字符串时：

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_end",
    "tool_name": "query_pageindex",
    "tool_call_id": "call_xxx",
    "status": "error",
    "error": "Error querying PageIndex: Failed to get chat completion: {\"detail\":\"LimitReached\"}",
    "output_preview": "Error querying PageIndex: Failed to...",
    "output_raw": "Error querying PageIndex: Failed to get chat completion: {\"detail\":\"LimitReached\"}",
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "ts": "2025-03-08T06:15:28.071000+00:00"
  }
}
```

- `error`: 错误摘要（最多约 500 字符）
- 前端可据此显示红色工具盒

#### final

```json
{
  "code": 0,
  "data": {
    "type": "final",
    "answer": "以下为**知识库中可查证的泰国设厂案例**，均来自同一权威案例文件...",
    "fileurls": [],
    "id": "46",
    "answer_id": "46",
    "question_id": "45",
    "action": [],
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53"
  }
}
```

#### error

整体失败时（如 Session 不存在、运行时异常）：

```json
{
  "code": 1,
  "data": {
    "type": "error",
    "session_id": "ea7560e6-a8fe-4d5e-8e71-1e6695c4ed53",
    "message": "Session not found",
    "ts": "2025-03-08T06:15:28.071000+00:00"
  }
}
```

#### end

```json
{
  "code": 0,
  "data": true
}
```

- 收到 `data === true` 时表示流结束，可停止读取。

---

### 4.5 完整 SSE 流示例

一次「泰国设厂案例？」请求的典型事件顺序：

```
data: {"code": 0, "data": {"type": "progress", "phase": "analysis", "status": "running", "session_id": "xxx", "ts": "..."}}

data: {"code": 0, "data": {"type": "process", "subtype": "tool_start", "tool_name": "list_pageindex_documents", ...}}

data: {"code": 0, "data": {"type": "process", "subtype": "tool_end", "tool_name": "list_pageindex_documents", "status": "completed", "output_raw": "...", ...}}

data: {"code": 0, "data": {"type": "process", "subtype": "tool_start", "tool_name": "query_pageindex", "input": {"query": "...", "doc_ids": [...]}, ...}}

data: {"code": 0, "data": {"type": "process", "subtype": "tool_end", "tool_name": "query_pageindex", "status": "completed", "output_raw": "...", ...}}

data: {"code": 0, "data": {"type": "process", "subtype": "tool_start", "tool_name": "think_tool", "input": {"reflection": "..."}, ...}}

data: {"code": 0, "data": {"type": "process", "subtype": "tool_end", "tool_name": "think_tool", "status": "completed", "output_raw": "...", ...}}

data: {"code": 0, "data": {"type": "final", "answer": "以下为**知识库中可查证的泰国设厂案例**...", "answer_id": "46", ...}}

data: {"code": 0, "data": true}
```

---

## 5. 流式 Chat 与 Agent 工具调用过程

### 5.1 当前能力（已实现）

流式模式下，前端可获取：

| 事件 | 说明 |
|------|------|
| progress | 开始处理 |
| process (tool_start) | 工具开始调用，含 `tool_name`、`tool_call_id`、`input` |
| process (tool_end) | 工具返回，含 `tool_call_id`、`output_raw`、`output_preview`、`status` |
| final | 完整答案 |
| error | 失败信息 |
| end | 流结束 |

- **tool_call_id 配对**：`tool_start` 与 `tool_end` 使用相同 `tool_call_id`，前端可据此更新同一张工具卡片。
- **output_json**：当前为 `null`，后续 Phase 2 可解析 PageIndex 等工具的结构化返回。

### 5.2 实现说明

- 流式模式使用 `send_chat_message_stream` → `run_agent_stream`，基于 `agent.stream(stream_mode="updates")` 解析 model/tools 节点。
- 非流式模式仍使用 `run_agent` + `invoke()`，不推送 process 事件。


### 运行检查脚本你能看到结果范围
```
BASE="https://odi-knowledge-backend.vercel.app"

# 1. 健康检查
echo "=== 1. Health check ==="
curl -s "$BASE/health"

echo -e "\n\n=== 2. Create session ==="
SESSION_RESP=$(curl -s -X POST "$BASE/api/v1/sessions" -H "Content-Type: application/json" -d '{}')
echo "$SESSION_RESP" | head -c 500
SESSION_ID=$(echo "$SESSION_RESP" | jq -r '.data.id // empty')
echo -e "\nSESSION_ID=$SESSION_ID"

if [ -n "$SESSION_ID" ]; then
  echo -e "\n=== 3. Completions (stream, first 2K) ==="
  curl -N -s -X POST "$BASE/api/v1/completions" \
    -H "Content-Type: application/json" \
    -d "{\"session_id\": \"$SESSION_ID\", \"question\": \"知识库有哪些大类的资料？\", \"stream\": true}" \
    | head -c 2048
fi
```
```
qianping@QiandeMacBook-Pro company-research % uv run python test_run_agent_stream.py
Calling run_agent_stream with a simple question...
2026-03-08 14:15:18,583 INFO [agent.research.pageindex_cache] ✅ Loaded 19 PageIndex documents into cache
2026-03-08 14:15:18,874 INFO [agent.agent_adapter] [Agent] STREAM START user_message='有多少份文档？' (history_len=1)
2026-03-08 14:15:28,060 INFO [httpx] HTTP Request: POST https://smart-sales.cognitiveservices.azure.com/openai/deployments/gpt-5.2-chat/chat/completions?api-version=2025-04-01-preview "HTTP/1.1 200 OK"
2026-03-08 14:15:28,069 INFO [agent.agent_adapter] [Agent] process event subtype=tool_start tool=list_pageindex_documents tool_call_id=call_MxSPIafvyfbiGctAXjoc9rXg
[CALLBACK] subtype=tool_start tool=list_pageindex_documents tool_call_id=call_MxSPIafvyfbiGctAXjoc9rXg
2026-03-08 14:15:28,069 INFO [agent.agent_adapter] [Agent] tool_start tool_name=list_pageindex_documents tool_call_id=call_MxSPIafvyfbiGctAXjoc9rXg input={}
2026-03-08 14:15:28,071 INFO [agent.agent_adapter] [Agent] process event subtype=tool_end tool=list_pageindex_documents tool_call_id=call_MxSPIafvyfbiGctAXjoc9rXg
[CALLBACK] subtype=tool_end tool=list_pageindex_documents tool_call_id=call_MxSPIafvyfbiGctAXjoc9rXg
2026-03-08 14:15:28,071 INFO [agent.agent_adapter] [Agent] tool_end tool_name=list_pageindex_documents tool_call_id=call_MxSPIafvyfbiGctAXjoc9rXg output_len=6046 preview=Available PageIndex Knowledge Base Documents (id | name | description):

**pi-cmmhbhu7601pafaqnqxypm18h**: Guide直接投资和间接…
2026-03-08 14:15:36,247 INFO [httpx] HTTP Request: POST https://smart-sales.cognitiveservices.azure.com/openai/deployments/gpt-5.2-chat/chat/completions?api-version=2025-04-01-preview "HTTP/1.1 200 OK"
2026-03-08 14:15:36,248 INFO [agent.agent_adapter] [Agent] final AIMessage len=184 preview=根据当前 **PageIndex 知识库文档清单**统计：

- **共有 20 份文档**

**知识来源说明：**  
- 来源：PageIndex 知识…
2026-03-08 14:15:36,249 INFO [agent.agent_adapter] [Agent] STREAM END response_len=184

Final answer length: 184
Collected 2 process events
  1. tool_start list_pageindex_documents call_MxSPIafvyfbiGct...
  2. tool_end list_pageindex_documents call_MxSPIafvyfbiGct...
```

---

## 6. 汇总表

| 方法   | 路径                                   | 说明           |
|--------|----------------------------------------|----------------|
| GET    | `/health`                              | 健康检查       |
| POST   | `/api/v1/sessions`                     | 创建会话       |
| GET    | `/api/v1/sessions`                     | 会话列表       |
| GET    | `/api/v1/sessions/{session_id}`        | 获取单个会话   |
| PUT    | `/api/v1/sessions/{session_id}`        | 重命名会话     |
| PUT    | `/api/v1/sessions/{session_id}/status` | 更新会话状态   |
| DELETE | `/api/v1/sessions`                     | 删除会话       |
| GET    | `/api/v1/sessions/{session_id}/messages` | 消息列表     |
| POST   | `/api/v1/completions`                  | 聊天补全（流式/非流式） |

---

## 7. 字段命名约定

- API 请求/响应使用 snake_case：`session_id`、`file_urls`、`question_id`
- 序列化输出中部分字段使用小写：`fileurls`、`answer_id`、`question_id`（与现有前端约定一致）
