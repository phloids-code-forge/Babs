#!/usr/bin/env python3
"""
File system tools for Babs.

read_file  -- Tier 0: full autonomy, no approval needed.
write_file -- Tier 2: propose and wait, requires explicit approval.
"""

import logging
import os
from pathlib import Path

from src.supervisor.tools import Tool, ToolParameter, TrustTier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

read_file_tool = Tool(
    name="read_file",
    description=(
        "Read a file from the local filesystem and return its contents. "
        "Use this to inspect source code, config files, logs, or any text file. "
        "Binary files are not supported. Large files are truncated at 500 lines."
    ),
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Absolute or home-relative path to the file (e.g. ~/babs/src/supervisor/supervisor.py).",
            required=True,
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="First line to read, 1-indexed. Defaults to 1.",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="Last line to read, inclusive. Defaults to 500.",
            required=False,
            default=500,
        ),
    ],
    trust_tier=TrustTier.TIER_0,
)

write_file_tool = Tool(
    name="write_file",
    description=(
        "Write content to a file on the local filesystem. "
        "Creates the file (and parent directories) if they do not exist. "
        "Overwrites the file if it already exists. "
        "Requires phloid approval before executing."
    ),
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Absolute or home-relative path to the file to write.",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to write to the file.",
            required=True,
        ),
    ],
    trust_tier=TrustTier.TIER_2,
)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _resolve(path: str) -> Path:
    """Expand ~ and resolve to an absolute path."""
    return Path(os.path.expanduser(path)).resolve()


async def read_file(path: str, start_line: int = 1, end_line: int = 500) -> dict:
    resolved = _resolve(path)
    logger.info(f"read_file: {resolved} lines {start_line}-{end_line}")

    if not resolved.exists():
        return {"error": f"File not found: {resolved}"}

    if not resolved.is_file():
        return {"error": f"Not a file: {resolved}"}

    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    lines = text.splitlines()
    total = len(lines)

    # Clamp to valid range
    start = max(1, start_line)
    end = min(total, end_line)
    selected = lines[start - 1:end]

    truncated = end < total and end_line >= total  # were we actually limited?
    truncated = end_line < total  # caller asked for less than the whole file

    return {
        "path": str(resolved),
        "total_lines": total,
        "start_line": start,
        "end_line": end,
        "truncated": end < total,
        "content": "\n".join(selected),
    }


async def write_file(path: str, content: str) -> dict:
    resolved = _resolve(path)
    logger.info(f"write_file: {resolved} ({len(content)} chars)")

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "path": str(resolved),
            "bytes_written": len(content.encode("utf-8")),
            "status": "ok",
        }
    except Exception as e:
        logger.error(f"write_file failed: {e}")
        return {"error": str(e)}
