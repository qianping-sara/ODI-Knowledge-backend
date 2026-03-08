# Smart-Proposal-Backend 会话 API 分析与兼容方案

## 范围
目标：在当前项目（company-research）中构建一个新的 chatbot，在保持会话流程兼容的同时做以下调整：移除 `/sessions/init`、API 不再使用 proposal/deal 字段、采用标准鉴权，并保持 `chat_sessions`/`chat_messages` 表结构完全一致。本文总结目标 API、数据模型，并给出可执行的实现方案。

## 现有 Session API 概览（smart-proposal-backend）

### 认证与身份
- 只保留“正常鉴权”（建议标准 `Authorization: Bearer <token>` 或你现有的统一鉴权中间件）。
- 会话和消息归属校验基于鉴权后的用户身份（例如 `user_id`）。
- 非流式返回的错误格式为 `{ "code": <int>, "message": "..." }`。

### 目标端点（建议）
路由统一在 `/api/v1` 下，搜索在 `/api/v1/chat/search`。

#### 1) 创建会话
`POST /api/v1/sessions`
- 请求：可以为空体，或仅传 `{ "name": "..." }`（由你决定是否暴露 name）。
- 行为：
  - 基于当前用户创建 `chat_sessions`。
  - 不再依赖 `proposal_type`、`proposal_id`、`deal_id` 等 smart-proposal 专有字段。
- 返回：包含会话元数据与消息列表（新建时为空）。

#### 2) 重命名会话
`PUT /api/v1/sessions/{session_id}`
- 请求：`{ "name": "..." }`
- 返回：`success()`（无 payload）。

#### 3) 更新会话状态
`PUT /api/v1/sessions/{session_id}/status`
- 请求：`{ "status": "..." }`
- 返回：`success()`（无 payload）。

#### 4) 获取会话列表
`GET /api/v1/sessions`
- 查询参数：`page`、`page_size`、`orderby`、`desc`、`name`、`id`
- 行为：按用户过滤，返回包含消息的会话对象。
- 返回会话对象字段包含 `create_time`、`update_time`（毫秒），以及 RFC1123 `create_date`、`update_date`，并排除 `event` 消息。

#### 5) 批量删除会话
`DELETE /api/v1/sessions`
- 请求：`{ "ids": ["..."] }`
- 返回：归属校验通过后 `success()`。

#### 6) 更新消息反馈
`PUT /api/v1/sessions/{session_id}/messages/{message_id}`
- 请求：`{ "feedback": "...", "rate": 1 }`（任一字段即可）
- 返回：`success(message="updated")`。

#### 7) 聊天补全
`POST /api/v1/completions`
- 请求体（可选/必选混合）：
  - `session_id`（可选；缺失时新建会话）
  - `stream`（默认 true）
  - `content` 或 `question`（别名）
  - `file_urls`（列表）
  - `file_contents`（列表）
- 行为：
  - 持久化 user 消息，运行 chat flow，再持久化 assistant 消息。
  - 更新 `chat_states` 保存状态。
  - 默认 **流式输出**，除非显式关闭流式。
- 非流式返回示例：
  ```json
  {
    "answer": "...",
    "fileurls": [],
    "id": "<assistant_message_id>",
    "answer_id": "<assistant_message_id>",
    "question_id": "<user_message_id>",
    "feedback": null,
    "rate": null,
    "modify_log": [],
    "action": [],
    "session_id": "<session_id>"
  }
  ```

#### 8) 搜索
`GET /api/v1/chat/search`
- 查询：`query`、`status`、`page`、`page_size`（是否保留 `template`/`has_deal` 由你决定）。
- 行为：对 sessions、messages（可选 state）做检索；不依赖 deal_info。

### 代码中存在但未挂载的 legacy 路由
- `app/routes/sessions.py` 与 `app/routes/messages.py` 提供 `/api/sessions` 与 `/api/sessions/{session_id}/messages`。
- `app/main.py` 未 include。若前端依赖，需要在新服务中显式挂载。

### SSE 流式格式
会话聊天默认 **流式输出**（等同 `stream=true`）。
当流式输出时，响应为 `text/event-stream`，数据格式：
```
data: {"code":0,"data":{...}}

```
- 进度事件使用 `data.type = "progress"`，含 `phase`、`status`、`stage_key`、`stage_label`、`plan` 等。
- 最终事件 `data.type = "final"`，并携带完整 completion payload。
- 结束事件：`{"code":0,"data":true}`。
- 错误事件：`{ "code": 1, "data": { "type": "error", "message": "..." } }`。

### 数据模型（持久化契约）
- **必须保持一致**：`chat_sessions`、`chat_messages`（字段结构与 smart-proposal-backend 完全一致）。
- 可选：`chat_states`（如需持久化 agent 状态再引入）。
- 本次方案**不需要** `deal_info`。

### Alembic 对齐要点（chat_sessions / chat_messages）
以下为 smart-proposal-backend 的关键迁移与最终字段形态，建议以此为准保持完全一致：

- 关键迁移（与 chat 表结构相关）：
  - `20251028_140637_fccabbc49c63_create_chat_tables.py`（创建基础表）
  - `20251028_143103_b986dd6f1a5e_add_file_data_to_messages.py`（file_urls / legacy file_content）
  - `20251028_145926_cf0d4593318a_add_proposal_type_to_sessions.py`（proposal_type）
  - `20251102_154200_e1c2f4f6a3b7_add_file_contents_column.py` + `20251102_160500_f5c6a1bde321_drop_file_content_column.py`（file_contents 替代 file_content）
  - `20251114_100000_d4e5f6a7b8c9_add_user_data_to_chat_messages.py`（user_data -> 仅 chat_sessions 保留）
  - `20251114_150000_add_user_columns_to_chat_sessions.py`（user_id/user_name/user_mail）
  - `20251119_140000_add_status_to_chat_sessions.py` + `20251219_160500_make_chat_session_status_explicit.py`（status 默认 open 且非空）
  - `20251202_141500_add_feedback_and_rate_to_chat_messages.py`（feedback/rate）
  - `20251218_150000_add_modify_log_to_chat_messages.py`（modify_log 非空，默认空数组）
  - `20251219_170000_add_show_first_invoice_button_to_chat_messages.py` + `20251219_180000_add_calculate_invoice_to_chat_messages.py` + `20260113_120000_drop_invoice_flags_from_chat_messages.py`（已回滚，不保留）

- 最终字段（建议严格保持一致）：
  - `chat_sessions`：`id`(CHAR36, PK) / `name`(String255) / `proposal_type`(String255, 默认空) / `status`(String64, 非空默认 `open`) / `user_id` / `user_name` / `user_mail` / `user_data`(JSON) / `created_at` / `updated_at`。
  - `chat_messages`：`id`(int, PK) / `session_id`(CHAR36, FK) / `role`(String32) / `content`(Text) / `file_urls`(JSON, 非空) / `file_contents`(JSON, 非空) / `modify_log`(JSON, 非空) / `created_at` / `feedback`(Text) / `rate`(int)。
  - 索引：`chat_sessions.id` 唯一索引、`chat_sessions.user_id` 索引、`chat_messages.session_id` 索引。

### Chat flow 组织方式（新方案）
- `chat_service.send_chat_message`：
  - 保存 user 消息。
  - 将历史消息转为 LangChain messages（event 作为 HumanMessage）。
  - 加载 `chat_states`（如使用）。
  - 调用统一的 ChatFlow（无需按 proposal_type 分流）。
  - 保存 assistant 消息并落库状态。

## 可行性评估（在 company-research 中构建新 chatbot）

### 可行，工作量中等
当前仓库是 LangGraph deepagent 示例，没有 HTTP API、会话存储或认证。通过补充 FastAPI 层和最小持久化即可实现兼容。主要工作在于复刻响应契约和会话生命周期，而非 SME/ListCo 的业务逻辑本身。

### 需要补齐的关键缺口
1. API 层：当前 repo 没有 FastAPI app。
2. 持久化：没有 session/message/state 存储，需要实现（SQLite 或 MySQL）。
3. 认证：需要接入你现有的标准鉴权体系（不再使用自定义 `accesstoken`）。
4. 流式 SSE：需要与现有结构保持一致。
5. 搜索：可选，若保留则实现轻量检索。

## 兼容方案建议

### A) API 兼容层（保持路径与字段一致）
建议实现以下端点（路径与字段保持一致）：
- `/api/v1/sessions`
- `/api/v1/sessions/{id}`
- `/api/v1/sessions/{id}/status`
- `/api/v1/sessions`（GET，返回消息）
- `/api/v1/sessions`（DELETE）
- `/api/v1/sessions/{id}/messages/{message_id}`
- `/api/v1/completions`
- `/api/v1/chat/search`（如需搜索能力）

可选（如需兼容 legacy 客户端）：
- `/api/sessions` 与 `/api/sessions/{id}/messages`。

### B) 返回结构与字段对齐
- JSON 统一使用 `success()` / `error()` 结构。
- 字段命名保持一致：`fileurls`、`answer_id`、`question_id`、`action`、`modify_log`。
- 兼容字段别名：`content`/`question`、`file_urls`/`file_contents`。
- 会话列表返回需包含 `create_time`/`update_time`（毫秒）与 `create_date`/`update_date`（RFC1123）。

### C) SSE 流式对齐
- 使用 `text/event-stream`。
- **默认流式输出**，非流式仅作为可选补充。
- 发送 `progress` 事件（可简化实现）与最终 `final` 事件。
- 以 `{ "code": 0, "data": true }` 结束。

### D) Proposal 类型处理
- API 不再要求/接收 `proposal_type`、`proposal_id`、`deal_id` 等 smart-proposal 专有字段。
- 数据表结构保持一致时，可将 `proposal_type` 留空或写入固定默认值（不对业务产生影响）。

## 代码改造方案（实施步骤）

### Phase 1：最小可用兼容服务
1. 新增 FastAPI app（例如 `app/main.py`）。
2. 增加 `chat_sessions`、`chat_messages` 的模型与仓储（`chat_states` 按需引入）。
3. 实现与新目标一致的路由（不包含 `/sessions/init`，创建会话不依赖 proposal/deal 信息）。
4. 接入标准鉴权（例如 JWT/Session 或统一网关鉴权），不再使用 `accesstoken` 方案。
5. 连接现有 deep research agent：
   - 用 `agent/entry.py` 作为模型核心。
   - 通过 `send_chat_message` 服务封装对话与会话状态。
6. SSE 流式输出：至少实现 start -> final 的事件序列。

### Phase 2：增强能力（可选）
1. 搜索：
   - 实现基础搜索（sessions/messages/state），全文索引可后续再上。
2. 状态持久化：
   - 每次对话后写入 `chat_states`。
   - 如生成文件或预览，返回与现有结构一致的 `fileurls`。

### Phase 3：稳定性与测试
1. 为每个接口添加 payload 结构测试。
2. 用 SSE 客户端验证流式结构与终止事件。
3. 校验错误码与归属检查行为一致。

## 可行性结论
可行。当前仓库已有 LLM 逻辑，但缺少会话管理与 HTTP API。通过新增 FastAPI 层与轻量持久化即可实现兼容的会话 API。主要风险在认证接入，其余改动相对直接。

## 下一步建议
请确认前端实际会调用的接口范围（仅 `/api/v1/completions`，还是也包含会话管理与搜索），以及认证/数据库偏好，以便进一步落地改造方案。
