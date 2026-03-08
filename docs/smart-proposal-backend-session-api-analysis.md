# Smart-Proposal-Backend Session API Analysis and Compatibility Plan

## Scope
Goal: build a new chatbot in the current project (company-research) that follows the same session-flow API contract as `smart-proposal-backend`, with these requested adjustments: drop `/sessions/init`, remove proposal/deal fields from the API, use standard auth, and keep `chat_sessions`/`chat_messages` schema identical. This document summarizes the target API, data model, and a concrete plan for implementation.

## Summary of the Existing Session API (smart-proposal-backend)

### Authentication and identity
- Keep only standard auth (recommended `Authorization: Bearer <token>` or your existing auth middleware).
- Ownership checks are enforced by the authenticated user identity (e.g., `user_id`).
- Errors are JSON with `{ "code": <int>, "message": "..." }` for non-stream responses.

### Active endpoints (target)
Routes should live under `/api/v1`, with search under `/api/v1/chat/search`.

#### 1) Create session
`POST /api/v1/sessions`
- Request: can be empty or `{ "name": "..." }` (optional, if you want to allow naming on create).
- Behavior:
  - Creates `chat_sessions` for the current user.
  - No `proposal_type`, `proposal_id`, or `deal_id` is required or used.
- Response: session object with metadata and embedded messages (empty on create).

#### 2) Rename session
`PUT /api/v1/sessions/{session_id}`
- Request: `{ "name": "..." }`
- Response: `success()` with no payload.

#### 3) Update session status
`PUT /api/v1/sessions/{session_id}/status`
- Request: `{ "status": "..." }`
- Response: `success()` with no payload.

#### 4) List sessions
`GET /api/v1/sessions`
- Query: `page`, `page_size`, `orderby`, `desc`, `name`, `id`
- Behavior: filters by user, includes session messages in response payload.
- Response: list of session objects with fields like `create_time`, `update_time`, `create_date` (RFC1123), and `messages` (excluding `event` role).

#### 5) Delete sessions (bulk)
`DELETE /api/v1/sessions`
- Request: `{ "ids": ["..."] }`
- Response: `success()` if ownership validated.

#### 6) Update message feedback
`PUT /api/v1/sessions/{session_id}/messages/{message_id}`
- Request: `{ "feedback": "...", "rate": 1 }` (either field allowed)
- Response: `success(message="updated")`.

#### 7) Chat completions
`POST /api/v1/completions`
- Request body (mix of required/optional):
  - `session_id` (optional; if missing, a new session is created)
  - `stream` (default true)
  - `content` or `question` (alias)
  - `file_urls` (list)
  - `file_contents` (list)
- Behavior:
  - Persists user message, runs chat flow, persists assistant message.
  - Updates `chat_states` with the returned state.
  - Streaming is **default**; SSE progress events are emitted unless explicitly disabled.
- Non-stream response payload:
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

#### 8) Search
`GET /api/v1/chat/search`
- Query: `query`, `status`, `page`, `page_size` (keep `template`/`has_deal` only if you still need them).
- Behavior: search across sessions, messages (optionally state); no deal_info dependency.

### Legacy (present in code but not mounted in main app)
- `/api/sessions` and `/api/sessions/{session_id}/messages` exist in `app/routes/sessions.py` and `app/routes/messages.py`.
- These are not included in `app/main.py`. If a consumer relies on them, they must be explicitly mounted in a new server.

### Streaming format (SSE)
Streaming is **on by default** for chat; the server should treat `stream=true` as the default behavior.
When streaming, the server responds with `text/event-stream` and yields lines:
```
data: {"code":0,"data":{...}}

```
- Progress events use `data.type = "progress"` and include fields like `phase`, `status`, `stage_key`, `stage_label`, and `plan`.
- The final message includes `data.type = "final"` and the normal completion payload.
- A terminal event is sent with `{"code":0,"data":true}`.
- Errors are wrapped as `{ "code": 1, "data": { "type": "error", "message": "..." } }`.

### Data model (persistence contract)
- **Must remain identical**: `chat_sessions`, `chat_messages` (match smart-proposal-backend schema exactly).
- Optional: `chat_states` (only if you need persisted agent state).
- `deal_info` is **not** required for this new chatbot.

### Alembic alignment notes (chat_sessions / chat_messages)
Key migrations and final schema to keep identical:

- Key migrations affecting chat tables:
  - `20251028_140637_fccabbc49c63_create_chat_tables.py` (base tables)
  - `20251028_143103_b986dd6f1a5e_add_file_data_to_messages.py` (file_urls / legacy file_content)
  - `20251028_145926_cf0d4593318a_add_proposal_type_to_sessions.py` (proposal_type)
  - `20251102_154200_e1c2f4f6a3b7_add_file_contents_column.py` + `20251102_160500_f5c6a1bde321_drop_file_content_column.py`
  - `20251114_100000_d4e5f6a7b8c9_add_user_data_to_chat_messages.py` (user_data -> retained only on chat_sessions)
  - `20251114_150000_add_user_columns_to_chat_sessions.py` (user_id/user_name/user_mail)
  - `20251119_140000_add_status_to_chat_sessions.py` + `20251219_160500_make_chat_session_status_explicit.py` (status default open, non-null)
  - `20251202_141500_add_feedback_and_rate_to_chat_messages.py` (feedback/rate)
  - `20251218_150000_add_modify_log_to_chat_messages.py` (modify_log non-null, default empty array)
  - `20251219_170000_add_show_first_invoice_button_to_chat_messages.py` + `20251219_180000_add_calculate_invoice_to_chat_messages.py` + `20260113_120000_drop_invoice_flags_from_chat_messages.py` (rolled back; not kept)

- Final schema (keep exactly):
  - `chat_sessions`: `id`(CHAR36, PK) / `name`(String255) / `proposal_type`(String255, default empty) / `status`(String64, non-null default `open`) / `user_id` / `user_name` / `user_mail` / `user_data`(JSON) / `created_at` / `updated_at`.
  - `chat_messages`: `id`(int, PK) / `session_id`(CHAR36, FK) / `role`(String32) / `content`(Text) / `file_urls`(JSON, non-null) / `file_contents`(JSON, non-null) / `modify_log`(JSON, non-null) / `created_at` / `feedback`(Text) / `rate`(int).
  - Indexes: unique `chat_sessions.id`, index `chat_sessions.user_id`, index `chat_messages.session_id`.

### Chat flow orchestration (new plan)
- `chat_service.send_chat_message`:
  - Persists user message.
  - Converts history to LangChain messages (event treated as HumanMessage).
  - Loads `chat_states` if enabled.
  - Runs a unified chat flow (no proposal-type routing).
  - Persists assistant message, saves state.

## Feasibility Assessment (New Chatbot in company-research)

### Feasible with moderate integration effort
The current repo is a LangGraph deepagent example and does not expose any HTTP API, session persistence, or auth. Building a compatible session API is feasible by adding a FastAPI layer and minimal persistence. The main work is in reproducing the response contracts and session lifecycle rather than the internal SME/ListCo logic.

### Key gaps to bridge
1. API layer: no FastAPI app in current repo; needs to be added.
2. Persistence: no session/message/state storage; must be implemented (SQLite or MySQL).
3. Auth: integrate your standard auth (no custom `accesstoken` flow).
4. Streaming: need SSE-compatible event stream with the same structure.
5. Search: optional, implement a lightweight version if required.

## Proposed Compatibility Plan

### A) API compatibility layer (same endpoints and payloads)
Implement the following contract (same paths, fields, default behavior):
- `/api/v1/sessions`
- `/api/v1/sessions/{id}`
- `/api/v1/sessions/{id}/status`
- `/api/v1/sessions` (GET with messages embedded)
- `/api/v1/sessions` (DELETE)
- `/api/v1/sessions/{id}/messages/{message_id}`
- `/api/v1/completions`
- `/api/v1/chat/search` (if search is required)

Optional (if you want parity with hidden routes):
- `/api/sessions` and `/api/sessions/{id}/messages`.

### B) Response and payload shape alignment
- Use the same `success()` / `error()` envelope for JSON responses.
- Preserve field names exactly: `fileurls`, `answer_id`, `question_id`, `action`, `modify_log`.
- Preserve alias support for `content` vs `question`, and `file_urls`/`file_contents`.
- Preserve `create_time`/`update_time` (ms) and RFC1123 `create_date`/`update_date` fields in session responses.

### C) Streaming behavior alignment
- Use SSE with `text/event-stream`.
- **Streaming is the default** for chat responses; non-streaming is optional.
- Emit `progress` events (even if simplified) and a final event with `type: "final"`.
- Terminate stream with `{ "code": 0, "data": true }`.

### D) Proposal-type handling
- The API should not require or accept `proposal_type`, `proposal_id`, or `deal_id`.
- Keep the `proposal_type` column in the DB (schema parity), but leave it empty or set a fixed default.

## Code Adaptation Plan (Implementation Strategy)

### Phase 1: Minimal compatibility server
1. Add a FastAPI app in this repo (new module, e.g., `app/main.py`).
2. Add models and repositories matching `chat_sessions` and `chat_messages` (`chat_states` only if you need persisted state).
3. Implement routes aligned with the new target (no `/sessions/init`, no proposal/deal payloads).
4. Integrate standard auth (JWT/session or your existing gateway), no custom `accesstoken` flow.
5. Wire the LLM:
   - Use the existing deep research agent from `agent/entry.py`.
   - Wrap it behind a `send_chat_message` service that accepts session history and returns assistant content.
6. Implement SSE streaming with a minimal progress sequence (start -> final).

### Phase 2: Enhancements (optional)
1. Search:
   - Implement a basic search on sessions/messages/state. Full-text can be deferred.
2. State persistence:
   - Store agent state in `chat_states` after each response.
   - Return file URLs or preview artifacts if your agent generates files.

### Phase 3: Hardening and testing
1. Add tests that validate payload shapes for each endpoint.
2. Validate streaming semantics with an SSE client.
3. Ensure consistent error codes and ownership checks.

## Feasibility Verdict
The plan is feasible. The current repo already has the core LLM agent logic but lacks session management and HTTP endpoints. By layering a FastAPI service and a lightweight persistence model, you can match the session API without replicating SME/ListCo business logic. The main risk is auth integration; everything else is straightforward.

## Recommended Next Step
Confirm which endpoints your client will actually call (e.g., only `/api/v1/completions` or also session management and search). That determines whether we implement search and persisted state now or later.
