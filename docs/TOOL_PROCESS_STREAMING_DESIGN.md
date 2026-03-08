# 主 Agent 工具调用过程流式暴露设计方案

> 目标：在流式 Chat API 中暴露主 Agent 调用 PageIndex 等工具的过程，使前端能展示「Tools: Find relevant documents Completed」及展开的 JSON 结果。

---

## 1. 现状与需求

### 1.1 当前流程

```
用户请求 → completions (stream=true)
         → progress_event（一次）
         → run_agent(messages)  [agent.invoke 阻塞执行]
           → 内部多次调用: list_pageindex_documents, query_pageindex, think_tool
           → PageIndex 可能耗时 47s+，期间无任何事件
         → final_event（完整 answer）
         → end_event
```

- **问题**：工具调用过程对前端不可见，用户无法感知「正在查文档」「查到了哪些结果」。
- **需求**：前端能收到类似截图的体验：
  - 每条工具调用：名称、状态（进行中/已完成）
  - 可展开查看工具返回的 JSON（如 PageIndex 的 `docs` 列表）。

### 1.2 技术基础与 stream_mode 选择

| 组件 | 能力 |
|------|------|
| **deepagents** | 基于 LangGraph，支持 `agent.stream(stream_mode="updates"|"messages"|"custom", subgraphs=True)` |
| **stream_mode="updates"** | 按节点粒度输出，可拿到 model 节点（含 tool_calls）和 tools 节点（含 tool result） |
| **stream_mode="messages"** | 流式推送消息块，可在模型写完 tool_calls 前预报「即将调用某工具」 |
| **stream_mode="custom"** | 工具内 `get_stream_writer()` 发送增量输出（如 PageIndex 流式内容） |

**选用 `updates` 模式**：工具执行开始后再展示即可，结束时一次性展示完整返回。实现简单、结构清晰。

| 模式 | 适用场景 | 本方案 |
|------|----------|--------|
| updates | 节点级快照：tool start/end | ✅ 采用 |
| messages | 模型生成 tool_calls 时即预报 | 不需要 |
| custom | 工具内部增量流式（如 PageIndex 逐字输出） | 不需要 |

---

## 2. 设计目标

1. **SSE 事件扩展**：在现有 `progress` / `final` / `error` / `end` 基础上，增加 `process` 事件。
2. **process 事件语义**：表示单次工具调用的开始（tool_start）、完成（tool_end，含 status: completed/error）。
3. **前端可展示**：工具名、状态、输入、完整输出（结束时一次性展示，可折叠/展开 JSON）。

---

## 3. SSE process 事件格式

### 3.1 工具开始 (tool_start)

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_start",
    "tool_name": "query_pageindex",
    "tool_call_id": "call_xxx",
    "input": {
      "query": "泰国设厂案例有哪些？",
      "doc_ids": ["pi-cmmc1cdkg00e50eob5q368b4r", "pi-cmmc1qam500130iob0fv43k5s"]
    },
    "session_id": "uuid",
    "ts": "2025-01-15T12:00:00.000000Z"
  }
}
```

### 3.2 工具完成 (tool_end)

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_end",
    "tool_name": "query_pageindex",
    "tool_call_id": "call_xxx",
    "status": "completed",
    "output_preview": "我来帮您查找文档中关于中国企业在泰国设厂的典型案例...",
    "output_raw": "完整返回文本，前端可折叠展示",
    "output_json": {
      "success": true,
      "docs": [
        {
          "id": "pi-cmmez3de80dck0nqpkwdwvmzh",
          "name": "Dezshira_BI_Case Study_Power Tools Relocate VN.pdf",
          "description": "电动工具制造商从中国迁往越南...",
          "pageNum": 3,
          "status": "completed"
        }
      ]
    },
    "elapsed_ms": 47986,
    "session_id": "uuid",
    "ts": "2025-01-15T12:00:00.000000Z"
  }
}
```

- `output_json`：当工具返回可解析为 JSON 时填充，便于前端做结构化展示；否则可为 `null`。
- `output_preview`：前 200 字符摘要，用于折叠态展示。

### 3.3 工具错误 (tool_error)

当工具内部捕获异常并返回错误信息字符串时，仍会作为 tool 结果返回。需识别此类「成功返回的错误内容」，将 `status` 设为 `"error"`，前端可显示红色工具盒：

```json
{
  "code": 0,
  "data": {
    "type": "process",
    "subtype": "tool_end",
    "tool_name": "query_pageindex",
    "tool_call_id": "call_xxx",
    "status": "error",
    "error": "Failed to get chat completion: {\"detail\":\"LimitReached\"}",
    "output_raw": "Error querying PageIndex: ...",
    "session_id": "uuid",
    "ts": "2025-01-15T12:00:00.000000Z"
  }
}
```

**实现要点**：工具内部应 `try/except` 捕获异常，返回错误字符串而非重新抛出，否则 Graph 会中断。识别逻辑：若 `output_raw` 以 `"Error "` 等关键字开头，或可解析出 `{"success": false}`，则标记 `status: "error"`。

### 3.4 tool_call_id 配对（重要）

**必须**：`tool_start` 与 `tool_end` 携带相同的 `tool_call_id`。

- 并发多工具调用时，顺序不可靠，只能靠 `tool_call_id` 配对。
- 前端用此 ID 更新**同一张**工具卡片状态，而非每次 tool_end 都追加新卡片。

---

## 4. 实现方案

### 4.1 方案概览

| 阶段 | 内容 | 复杂度 |
|------|------|--------|
| **Phase 1** | 用 `agent.stream(stream_mode="updates")` 替代 `invoke()`，解析 model / tools 节点，发出 tool_start / tool_end | 中 |
| **Phase 2** | 工具返回结构化解析（output_json），适配 PageIndex 返回格式；识别错误返回并标记 tool_error | 低 |

仅用 `updates` 模式，工具结束时一次性展示返回内容即可，无需 `custom` 模式下的工具内流式。

### 4.2 Phase 1：Tool Start / End 的获取时机

`stream_mode="updates"` 按节点粒度返回，每个 chunk 对应一个节点的输出。无需「推断」：

| 节点 | 产出 | 处理 |
|------|------|------|
| **model_request**（或 call_model） | `message.tool_calls` 有值时，表示模型决定调用工具 | **立即**发 `tool_start`，含 `tool_name`、`input`（来自 `args`）、`tool_call_id` |
| **tools** | `message.type == "tool"` 时，表示工具执行完毕 | **立即**发 `tool_end`，含 `tool_call_id`、`output_raw`（content） |

**配对逻辑**：`tool_end` 的 `msg.tool_call_id` 与 `tool_start` 的 `tc["id"]` 一致，前端用 `tool_call_id` 更新同一张卡片。

**stream 解析伪代码：**

```python
for namespace, chunk in agent.stream(
    {"messages": messages},
    stream_mode="updates",
    subgraphs=False,
):
    for node_name, data in chunk.items():
        # Model 节点输出：拿到 tool_calls 即发 tool_start
        if node_name in ("model_request", "call_model"):
            for msg in data.get("messages", []):
                for tc in getattr(msg, "tool_calls", []):
                    callback(tool_start_event(
                        tool_call_id=tc["id"],
                        tool_name=tc["name"],
                        input=tc.get("args", {}),
                    ))

        # Tools 节点输出：拿到 tool message 即发 tool_end
        elif node_name == "tools":
            for msg in data.get("messages", []):
                if getattr(msg, "type", None) == "tool":
                    callback(tool_end_event(
                        tool_call_id=msg.tool_call_id,
                        tool_name=msg.name,
                        output_raw=msg.content,
                    ))
```

**改动点：**

1. **agent_adapter.py**：新增 `run_agent_stream(messages, event_callback)`，使用上述解析逻辑，流结束后返回最终 answer。
2. **services/chat_service.py**：新增 `send_chat_message_stream(db, session_id, payload, event_queue)`，调用 `run_agent_stream` 并传入 queue。
3. **api/routes/completions.py**：`run_flow` 中调用 `send_chat_message_stream`，将 process 事件 `put` 到 queue。

### 4.3 Phase 2：output_json、output_preview 与 tool_error 识别

- **output_raw / output_preview**：
  - `output_raw` = 工具返回的原始字符串。
  - `output_preview` = 前 200 字符，用于折叠态展示。
  - 尝试解析 `output_raw` 为 JSON，若为 PageIndex 格式（`{content:[{type:"text", text:"..."}]}` 或内含 `docs`），则填入 `output_json`；否则 `output_json: null`。

- **tool_error 语义化**：工具内部应捕获异常并返回错误字符串（如 `"Error querying PageIndex: ..."`），避免抛出让 Graph 中断。识别逻辑：
  - `output_raw` 以 `"Error "` 等关键字开头，或
  - 可解析为 `{"success": false}` 等错误结构
  → 将 `status` 设为 `"error"`，`subtype` 仍为 `tool_end`，前端显示红色工具盒。

---

## 5. 数据流与调用链

```
POST /api/v1/completions (stream=true)
  → completions.run_flow()
     → queue.put(progress_event)
     → send_chat_message_stream(db, session_id, payload, queue)
        → run_agent_stream(messages, callback)
           → for namespace, chunk in agent.stream(stream_mode="updates"):
                → 解析 chunk["tools"] / chunk["model_request"]
                → callback(process_event)  # tool_start / tool_end
           → return final_answer
     → queue.put(final_event)
     → queue.put(end_event)
  → event_stream() 消费 queue，yield SSE
```

---

## 6. 前端消费建议

1. **按 tool_call_id 配对**：用 `tool_call_id` 作为卡片唯一键。收到 `tool_start` 创建新卡片；收到 `tool_end` 时根据 `tool_call_id` 更新同一张卡片，而非追加新卡片。
2. **折叠/展开**：`tool_end` 后标记完成，支持展开查看 `output_raw` 或 `output_json`。
3. **错误态**：`status: "error"` 时展示红色工具盒，显示 `error` 字段，并可折叠查看 `output_raw`（如有）。

---

## 7. 兼容性与风险

| 项 | 说明 |
|----|------|
| **非流式 stream=false** | 不改动，仍用 `invoke()`，不推送 process 事件。 |
| **向后兼容** | 仅新增 `type: "process"` 事件，原有 progress/final/error/end 不变。 |
| **性能** | stream 模式下会有更多 SSE 事件，带宽略增；JSON 体积可控（output_preview 截断、output_raw 可设 max 长度）。 |
| **工具异常** | 工具内部需 try/except 返回错误字符串，否则 Graph 会中断；pageindex_cache 已满足此约定。 |
| **流异常** | 若 agent.stream 中途抛错，需确保能发出 error_event 并 end_event，避免流悬挂。 |

---

## 8. 实施步骤建议

1. **Step 1**：在 agent_adapter 中实现 `run_agent_stream`，用 `stream_mode="updates"` 解析 model_request / tools 节点，打印日志验证能拿到 tool_calls 和 tool result，并确保 `tool_call_id` 一致。
2. **Step 2**：定义 `process_event` 构造函数（tool_start / tool_end），在 chat_service 和 completions 中接入 queue，端到端验证 SSE 能收到 process 事件。
3. **Step 3**：完善 output_preview、output_json 解析及 tool_error 识别逻辑；确认 pageindex_cache / tools 在异常时返回字符串而非抛出。
