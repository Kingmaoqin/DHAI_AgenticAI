"""End-to-end test: start both agents, run 1 evaluation task."""

import asyncio
import os
import signal
import subprocess
import sys
import time

import httpx

PURPLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FWA_DIR = os.path.join(os.path.dirname(PURPLE_DIR), "FieldWorkArena-GreenAgent")

PURPLE_VENV = os.path.join(PURPLE_DIR, ".venv", "bin", "python")
GREEN_VENV = os.path.join(FWA_DIR, ".venv", "bin", "python")


async def wait_for_server(url: str, timeout: int = 30) -> bool:
    async with httpx.AsyncClient(timeout=5) as client:
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = await client.get(f"{url}/.well-known/agent.json")
                if r.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.ReadError):
                pass
            await asyncio.sleep(1)
    return False


async def main():
    procs = []
    env = os.environ.copy()
    # Load .env from purple agent dir
    dotenv_path = os.path.join(PURPLE_DIR, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()

    try:
        # 1. Start purple agent
        print("Starting Purple Agent on :9019 ...")
        purple_env = env.copy()
        purple_env["PYTHONPATH"] = os.path.join(PURPLE_DIR, "src")
        procs.append(subprocess.Popen(
            [PURPLE_VENV, "-m", "agent.server", "--host", "127.0.0.1", "--port", "9019"],
            env=purple_env,
            stdout=open("/tmp/purple_e2e.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ))

        # 2. Start green agent
        print("Starting Green Agent on :9009 ...")
        procs.append(subprocess.Popen(
            [GREEN_VENV, "-m", "fieldworkarena.agent.fwa_green_agent",
             "--host", "127.0.0.1", "--port", "9009"],
            env=env,
            cwd=FWA_DIR,
            stdout=open("/tmp/green_e2e.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ))

        # 3. Wait for both
        print("Waiting for agents...")
        for name, port in [("Purple", 9019), ("Green", 9009)]:
            ok = await wait_for_server(f"http://127.0.0.1:{port}")
            if ok:
                print(f"  {name} agent ready")
            else:
                print(f"  TIMEOUT: {name} agent not ready")
                print(f"  Purple log: {open('/tmp/purple_e2e.log').read()[-500:]}")
                print(f"  Green log: {open('/tmp/green_e2e.log').read()[-500:]}")
                sys.exit(1)

        # 4. Run evaluation client
        print("\nRunning evaluation (1 task, custom target)...")
        scenario = os.path.join(FWA_DIR, "scenarios", "fwa", "scenario_test.toml")
        result = subprocess.run(
            [GREEN_VENV, "-m", "fieldworkarena.agent.client", scenario],
            env=env,
            cwd=FWA_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        print("STDOUT:", result.stdout[-2000:] if result.stdout else "(empty)")
        print("STDERR:", result.stderr[-1000:] if result.stderr else "(empty)")
        print("Return code:", result.returncode)

        # 5. Check results
        print("\n=== Agent Logs ===")
        print("Purple agent (last 30 lines):")
        with open("/tmp/purple_e2e.log") as f:
            lines = f.readlines()
            for line in lines[-30:]:
                print("  ", line.rstrip())

        print("\nGreen agent (last 30 lines):")
        with open("/tmp/green_e2e.log") as f:
            lines = f.readlines()
            for line in lines[-30:]:
                print("  ", line.rstrip())

    finally:
        print("\nCleaning up...")
        for p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        time.sleep(1)
        for p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
