"""Step 1 verification: run run_agent_stream and check logs for tool_start/tool_end."""

import asyncio
import logging

from dotenv import load_dotenv
load_dotenv()

# Ensure agent logs are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from agent.agent_adapter import run_agent_stream


async def main():
    events = []

    def on_event(evt):
        events.append(evt)
        print(f"[CALLBACK] subtype={evt.get('subtype')} tool={evt.get('tool_name')} tool_call_id={evt.get('tool_call_id')}")

    print("Calling run_agent_stream with a simple question...")
    answer = await run_agent_stream(
        [{"role": "user", "content": "有多少份文档？"}],
        event_callback=on_event,
    )
    print(f"\nFinal answer length: {len(answer)}")
    print(f"Collected {len(events)} process events")
    for i, e in enumerate(events):
        print(f"  {i+1}. {e.get('subtype')} {e.get('tool_name')} {e.get('tool_call_id', '')[:20]}...")


if __name__ == "__main__":
    asyncio.run(main())
