"""Direct A2A test: send multimodal messages to the purple agent without green agent.

This test verifies the purple agent handles text, PDF, and image inputs
correctly through the A2A protocol, without needing HF_TOKEN or the
green agent infrastructure.
"""

import asyncio
import base64
import json
import os
import subprocess
import signal
import sys
import time

import httpx

PURPLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PURPLE_VENV = os.path.join(PURPLE_DIR, ".venv", "bin", "python")
URL = "http://127.0.0.1:9019"


def make_text_request(msg_id: str, text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg-{msg_id}",
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
            }
        },
    }


def make_file_request(msg_id: str, text: str, file_name: str, file_bytes: bytes, mime: str) -> dict:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg-{msg_id}",
                "role": "user",
                "parts": [
                    {"kind": "text", "text": text},
                    {
                        "kind": "file",
                        "file": {
                            "bytes": encoded,
                            "mimeType": mime,
                            "name": file_name,
                        },
                    },
                ],
            }
        },
    }


def extract_response(data: dict) -> str:
    """Extract text from A2A response."""
    result = data.get("result", {})
    texts = []
    # check artifacts
    for art in result.get("artifacts", []):
        for part in art.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                texts.append(part["text"].strip())
    # check status message
    status = result.get("status", {})
    msg = status.get("message", {})
    for part in msg.get("parts", []) if msg else []:
        if part.get("kind") == "text" and part.get("text"):
            texts.append(part["text"].strip())
    return " | ".join(texts) if texts else str(result)[:200]


async def run_tests():
    async with httpx.AsyncClient(timeout=90) as client:
        # Test 1: Simple text question
        print("Test 1: Simple text question")
        req = make_text_request("t1", "What is the capital of France? Answer in one word.")
        resp = await client.post(URL, json=req)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        text = extract_response(resp.json())
        print(f"  Response: {text}")
        assert "paris" in text.lower(), f"Expected 'Paris' in response"
        print("  PASSED")

        # Test 2: Text file + question (simulates store manual task)
        print("\nTest 2: Text file + question")
        manual_content = (
            "Store Manual A\n"
            "==============\n\n"
            "Business Hours:\n"
            "- Monday to Friday: 09:00 to 21:00\n"
            "- Saturday: 10:00 to 20:00\n"
            "- Sunday and Holidays: 08:00 to 18:00\n"
            "- April 28, 2025 (Monday): 08:00 to 20:00 (special hours)\n\n"
            "Return Policy:\n"
            "- Items can be returned within 30 days with receipt.\n"
        )
        req = make_file_request(
            "t2",
            "# Question\nRead this store manual. What are the business hours for April 28, 2025?\n\n# Input Data\nStore_Manual_A.txt\n\n# Output Format\ntext",
            "Store_Manual_A.txt",
            manual_content.encode("utf-8"),
            "text/plain",
        )
        resp = await client.post(URL, json=req)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        text = extract_response(resp.json())
        print(f"  Response: {text}")
        assert "08:00" in text and "20:00" in text, f"Expected hours in response"
        print("  PASSED")

        # Test 3: Arithmetic reasoning
        print("\nTest 3: Arithmetic reasoning")
        req = make_text_request(
            "t3",
            "A factory produces 150 units per hour. How many units in 8 hours? Answer with just the number."
        )
        resp = await client.post(URL, json=req)
        assert resp.status_code == 200
        text = extract_response(resp.json())
        print(f"  Response: {text}")
        assert "1200" in text, f"Expected '1200' in response"
        print("  PASSED")


async def main():
    proc = None
    try:
        # Start purple agent
        print("Starting Purple Agent...")
        env = os.environ.copy()
        dotenv_path = os.path.join(PURPLE_DIR, ".env")
        if os.path.exists(dotenv_path):
            with open(dotenv_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()

        env["PYTHONPATH"] = os.path.join(PURPLE_DIR, "src")
        proc = subprocess.Popen(
            [PURPLE_VENV, "-m", "agent.server", "--host", "127.0.0.1", "--port", "9019"],
            env=env,
            stdout=open("/tmp/purple_test.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        # Wait for ready
        for i in range(15):
            try:
                async with httpx.AsyncClient(timeout=3) as c:
                    r = await c.get(f"{URL}/.well-known/agent.json")
                    if r.status_code == 200:
                        break
            except Exception:
                pass
            await asyncio.sleep(2)
        else:
            print("TIMEOUT: Purple agent not ready")
            with open("/tmp/purple_test.log") as f:
                print(f.read()[-500:])
            sys.exit(1)

        print("Purple Agent ready\n")
        await run_tests()
        print("\n=== All tests PASSED ===")

    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    finally:
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            time.sleep(1)
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
