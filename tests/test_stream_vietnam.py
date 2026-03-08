"""Test streaming with PageIndex-heavy query (Vietnam industrial parks).

Verifies that SSE stream completes without premature disconnect during
long-running query_pageindex calls. Run against local or remote API:

  BASE_URL=http://localhost:8000 uv run python tests/test_stream_vietnam.py
  BASE_URL=https://odi-knowledge-backend.vercel.app uv run python tests/test_stream_vietnam.py
"""

import json
import os
import sys

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_BASE = f"{BASE_URL}/api/v1"


def main() -> int:
    print(f"Testing streaming with PageIndex query against {BASE_URL}")
    print("Question: 越南工业园区有哪些？")
    print("=" * 60)

    # 1. Create session
    r = requests.post(
        f"{API_BASE}/sessions",
        json={},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        print(f"❌ Create session failed: {data}")
        return 1
    session_id = data["data"]["id"]
    print(f"✅ Session: {session_id}")

    # 2. Stream completions (no truncation)
    # (connect_timeout, read_timeout) - read must allow 60s+ gaps during PageIndex
    print("\n📤 Streaming (waiting for final + end)...")
    r = requests.post(
        f"{API_BASE}/completions",
        json={
            "session_id": session_id,
            "question": "越南工业园区有哪些？",
            "stream": True,
        },
        stream=True,
        timeout=(30, 180),
    )
    if r.status_code != 200:
        print(f"❌ Request failed {r.status_code}: {r.text[:500]}")
        return 1

    events = []
    final_answer = None
    got_end = False
    for line in r.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8")
        if line.startswith(":"):
            events.append(("keepalive", None))
            continue
        if not line.startswith("data: "):
            continue
        raw = line[6:]
        if raw == "[DONE]":
            break
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            events.append(("parse_error", raw[:80]))
            continue
        payload = event.get("data")
        if payload is True:
            got_end = True
            events.append(("end", None))
            break
        if isinstance(payload, dict):
            ev_type = payload.get("type", "")
            events.append((ev_type, payload))
            if ev_type == "final" and "answer" in payload:
                final_answer = payload["answer"]

    keepalives = sum(1 for t, _ in events if t == "keepalive")
    print(f"  Events: {len(events)} (keepalives: {keepalives})")
    print(f"  Got final: {final_answer is not None}")
    print(f"  Got end:   {got_end}")

    if not got_end:
        print("\n❌ FAIL: Stream ended without end event (connection likely dropped)")
        return 1
    if final_answer is None:
        print("\n❌ FAIL: No final answer received")
        return 1

    print(f"\n✅ PASS: Full stream received, answer length={len(final_answer)}")
    print("\nAnswer preview:")
    print(final_answer[:500] + ("..." if len(final_answer) > 500 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
