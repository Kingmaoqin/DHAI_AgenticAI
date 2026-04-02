"""Smoke test: start the purple agent server and check agent card is served."""

import asyncio
import sys
import time

import httpx


async def check_agent_card(url: str, retries: int = 10, delay: float = 1.0):
    """Poll the agent card endpoint until ready."""
    async with httpx.AsyncClient(timeout=10) as client:
        for i in range(retries):
            try:
                # A2A agent card is served at /.well-known/agent.json
                resp = await client.get(f"{url}/.well-known/agent.json")
                if resp.status_code == 200:
                    card = resp.json()
                    print(f"Agent card retrieved successfully:")
                    print(f"  Name: {card.get('name')}")
                    print(f"  Version: {card.get('version')}")
                    print(f"  Skills: {[s.get('name') for s in card.get('skills', [])]}")
                    print(f"  Input modes: {card.get('defaultInputModes')}")
                    return True
            except (httpx.ConnectError, httpx.ReadError):
                pass
            print(f"  Waiting for server... ({i+1}/{retries})")
            await asyncio.sleep(delay)
    return False


async def send_text_message(url: str):
    """Send a simple text-only A2A message and check response."""
    async with httpx.AsyncClient(timeout=60) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-test-1",
                    "role": "user",
                    "parts": [
                        {"kind": "text", "text": "What is 2 + 3? Answer with just the number."}
                    ],
                }
            },
        }
        resp = await client.post(url, json=payload)
        print(f"\nText message test:")
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # extract response text from result
            result = data.get("result", {})
            artifacts = result.get("artifacts", [])
            for art in artifacts:
                for part in art.get("parts", []):
                    if part.get("kind") == "text":
                        print(f"  Response: {part.get('text', '')[:200]}")
            return True
        else:
            print(f"  Error: {resp.text[:300]}")
            return False


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9019"
    print(f"Testing purple agent at {url}")

    ok = await check_agent_card(url)
    if not ok:
        print("FAIL: Could not reach agent card")
        sys.exit(1)

    ok = await send_text_message(url)
    if not ok:
        print("FAIL: Text message test failed")
        sys.exit(1)

    print("\nAll smoke tests PASSED")


if __name__ == "__main__":
    asyncio.run(main())
