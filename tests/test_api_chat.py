"""Test script for PageIndex-powered chat API."""

import json
import time

import requests

# API configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Set True to print all SSE events and payload details
VERBOSE_SSE = True

def create_session():
    """Create a new chat session."""
    response = requests.post(
        f"{API_BASE}/sessions",
        json={"title": "PageIndex Test Session"}
    )
    response.raise_for_status()
    result = response.json()
    session = result['data']  # API returns {"code": 200, "data": {...}}
    print(f"✅ Created session: {session['id']}")
    return session['id']

def send_message_streaming(session_id, message):
    """Send a message and stream the response.

    Server sends: progress → final (full answer) → end.
    API format: {"code": 0, "data": {...}} where data may be:
    - {"type": "progress", ...}
    - {"type": "final", "answer": "...", ...}
    - True (end)
    """
    print(f"\n{'='*60}")
    print(f"📤 User: {message}")
    print(f"{'='*60}")

    response = requests.post(
        f"{API_BASE}/completions",
        json={
            "session_id": session_id,
            "question": message,
            "stream": True,
        },
        stream=True,
    )

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        response.raise_for_status()

    if VERBOSE_SSE:
        print("\n[SSE] Streaming events (PageIndex returns are logged on server):\n")
    else:
        print("🤖 Assistant: ", end="", flush=True)

    full_response = ""
    event_count = 0
    for line in response.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                raw = line[6:]
                if raw == "[DONE]":
                    if VERBOSE_SSE:
                        print(f"\n[SSE] event #{event_count + 1}: [DONE]")
                    break
                try:
                    event = json.loads(raw)
                    event_count += 1
                    payload = event.get("data")
                    code = event.get("code", "")

                    if VERBOSE_SSE:
                        _print_sse_event(event_count, event, payload, code)

                    if payload is True:
                        break
                    if isinstance(payload, dict):
                        if payload.get("type") == "progress":
                            if not VERBOSE_SSE:
                                print(".", end="", flush=True)
                        elif payload.get("type") == "final" and "answer" in payload:
                            answer = payload["answer"]
                            if not VERBOSE_SSE:
                                print(answer, end="", flush=True)
                            full_response = answer
                        elif payload.get("type") == "error":
                            print(f"\n❌ Error: {payload.get('message', payload)}")
                except json.JSONDecodeError as e:
                    if VERBOSE_SSE:
                        print(f"\n[SSE] parse error: {e} raw={raw[:100]}...")

    if not VERBOSE_SSE:
        print()
    print()
    return full_response


def _print_sse_event(idx: int, event: dict, payload, code: int) -> None:
    """Print one SSE event with full details."""
    print(f"\n--- [SSE] event #{idx} code={code} ---")
    if payload is True:
        print("  data: True (end)")
        return
    if isinstance(payload, dict):
        ev_type = payload.get("type", "?")
        print(f"  type: {ev_type}")
        if ev_type == "progress":
            print(f"  phase: {payload.get('phase', '?')} status: {payload.get('status', '?')}")
            print(f"  session_id: {payload.get('session_id', '?')}")
        elif ev_type == "final":
            answer = payload.get("answer", "")
            print(f"  answer_id: {payload.get('answer_id')}")
            print(f"  question_id: {payload.get('question_id')}")
            print(f"  answer_len: {len(answer)}")
            print(f"  answer (full):\n{answer}")
        elif ev_type == "error":
            print(f"  message: {payload.get('message', payload)}")
        elif ev_type == "process":
            subtype = payload.get("subtype", "?")
            tool_name = payload.get("tool_name", "?")
            tool_call_id = (payload.get("tool_call_id") or "")[:24] + "..."
            print(f"  subtype: {subtype} tool_name: {tool_name} tool_call_id: {tool_call_id}")
            if subtype == "tool_start":
                print(f"  input: {payload.get('input', {})}")
            elif subtype == "tool_end":
                status = payload.get("status", "?")
                output_preview = (payload.get("output_preview") or "")[:120]
                print(f"  status: {status} output_preview: {output_preview}...")
        else:
            print(f"  payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}")
    else:
        print(f"  data: {payload}")

def send_message_non_streaming(session_id, message):
    """Send a message and get the full response."""
    print(f"\n{'='*60}")
    print(f"📤 User: {message}")
    print(f"{'='*60}")

    response = requests.post(
        f"{API_BASE}/completions",
        json={
            "session_id": session_id,
            "question": message,  # API expects 'question', not 'message'
            "stream": False  # Disable streaming
        }
    )

    # Print error details if request fails
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        response.raise_for_status()

    result = response.json()

    # API returns {"code": 200, "data": {"answer": "...", "answer_id": "...", ...}}
    data = result.get('data', {})
    assistant_response = data.get('answer', '')

    print(f"🤖 Assistant:\n{assistant_response}\n")
    return assistant_response

def get_session_messages(session_id):
    """Get all messages in a session."""
    response = requests.get(f"{API_BASE}/sessions/{session_id}")
    response.raise_for_status()
    result = response.json()

    # API returns {"code": 200, "data": {"messages": [...], ...}}
    session_data = result.get("data", {})
    messages = session_data.get("messages", [])

    print(f"\n📜 Session History ({len(messages)} messages):")
    for msg in messages:
        role_icon = "📤" if msg['role'] == 'user' else "🤖"
        content = msg.get('content', '')
        preview = content[:100] + "..." if len(content) > 100 else content
        print(f"{role_icon} {msg['role']}: {preview}")

    return messages

def main():
    """Run test scenarios."""
    print("🚀 Starting PageIndex Chat API Test")
    print(f"API URL: {BASE_URL}")
    print("="*60)
    
    # Test 1: Create session
    print("\n📋 Test 1: Create Session")
    session_id = create_session()
    
    # Test 2: Simple query (streaming)
    print("\n📋 Test 2: Simple Query (Streaming)")
    send_message_streaming(
        session_id,
        "泰国设厂案例?"
    )
    
    time.sleep(1)
    
    # # Test 3: Complex query (streaming - same as Test 2, shows progress/final events)
    # print("\n📋 Test 3: Complex Query (Streaming)")
    # send_message_streaming(
    #     session_id,
    #     "汽车零配件行业，去越南合适吗？规则和准入是什么？需要哪些流程和办理哪些证？"
    # )
    
    time.sleep(1)
    
    # # Test 4: Follow-up question
    # print("\n📋 Test 4: Follow-up Question (Streaming)")
    # send_message_streaming(
    #     session_id,
    #     "哪个区有政策扶持?"
    # )
    
    # Test 5: Get session history
    print("\n📋 Test 5: Get Session History")
    get_session_messages(session_id)
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to API server")
        print("Please start the server first:")
        print("  uv run uvicorn api.main:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

