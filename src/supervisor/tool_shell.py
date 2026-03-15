#!/usr/bin/env python3
"""
Shell execution tool for Babs.

shell -- Tier 2: propose and wait, requires explicit approval.

Runs a single shell command in a subprocess with a configurable timeout.
stdout and stderr are both captured and returned.
"""

import asyncio
import logging

from src.supervisor.tools import Tool, ToolParameter, TrustTier

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60  # seconds

shell_tool = Tool(
    name="shell",
    description=(
        "Run a shell command on the Spark host and return stdout and stderr. "
        "Use this for system inspection, running scripts, checking service status, "
        "manipulating files via command-line tools, or any task that requires a shell. "
        "Requires phloid approval before executing. "
        "Commands run as the 'dave' user with passwordless sudo available."
    ),
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="The shell command to run (passed to bash -c).",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description=f"Timeout in seconds. Defaults to {DEFAULT_TIMEOUT}. Max 300.",
            required=False,
            default=DEFAULT_TIMEOUT,
        ),
    ],
    trust_tier=TrustTier.TIER_2,
)


async def shell(command: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    timeout = min(int(timeout), 300)
    logger.info(f"shell: {command!r} (timeout={timeout}s)")

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "error": f"Command timed out after {timeout}s",
            }

        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }

    except Exception as e:
        logger.error(f"shell tool failed: {e}")
        return {"command": command, "returncode": -1, "stdout": "", "stderr": "", "error": str(e)}
