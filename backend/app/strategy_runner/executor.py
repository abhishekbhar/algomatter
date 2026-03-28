import asyncio
import json
import sys

MAX_CONCURRENT_WORKERS = 4
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)


async def run_subprocess(payload: dict, timeout: int = 60) -> dict:
    """Execute strategy code in a subprocess and return parsed output."""
    async with _semaphore:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "app.strategy_sdk.subprocess_entry",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdin_data = json.dumps(payload).encode()
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin_data),
                timeout=timeout,
            )
            if process.returncode != 0:
                return {
                    "orders": [], "cancelled_orders": [],
                    "state": {"user_state": payload.get("state", {}).get("user_state", {})},
                    "logs": [],
                    "error": {"type": "runtime", "message": f"Subprocess exited with code {process.returncode}: {stderr.decode()[:500]}", "traceback": ""},
                }
            return json.loads(stdout.decode())
        except asyncio.TimeoutError:
            process.kill()
            return {
                "orders": [], "cancelled_orders": [],
                "state": {"user_state": payload.get("state", {}).get("user_state", {})},
                "logs": [],
                "error": {"type": "timeout", "message": f"Strategy execution timed out after {timeout}s", "traceback": ""},
            }
        except Exception as e:
            return {
                "orders": [], "cancelled_orders": [],
                "state": {"user_state": payload.get("state", {}).get("user_state", {})},
                "logs": [],
                "error": {"type": "runtime", "message": str(e), "traceback": ""},
            }
