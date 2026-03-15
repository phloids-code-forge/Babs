#!/usr/bin/env python3
"""
Persistent thread storage for Babs using SQLite.

Conversation threads survive supervisor restarts. Threads are loaded lazily
(on first access) and saved after each complete request cycle.

Database: ~/babs-data/threads.db
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    thread_id  TEXT    NOT NULL,
    seq        INTEGER NOT NULL,
    message    TEXT    NOT NULL,  -- JSON
    created_at TEXT    NOT NULL,
    PRIMARY KEY (thread_id, seq)
);

CREATE TABLE IF NOT EXISTS thread_meta (
    thread_id  TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL
);
"""


class ThreadStore:
    """
    Sqlite-backed persistent store for conversation threads.

    Thread format matches what the supervisor already uses:
        List[Dict]  -- each dict has at minimum "role" and "content",
                       plus optional "tool_calls", "name", etc.
    """

    def __init__(self, db_path: str = "~/babs-data/threads.db"):
        self.db_path = Path(os.path.expanduser(db_path))
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Open the database and create tables if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        logger.info(f"ThreadStore initialized at {self.db_path}")

    def load(self, thread_id: str) -> List[Dict[str, Any]]:
        """Load all messages for a thread, ordered by seq. Returns [] if not found."""
        if self._conn is None:
            return []
        try:
            rows = self._conn.execute(
                "SELECT message FROM messages WHERE thread_id = ? ORDER BY seq",
                (thread_id,),
            ).fetchall()
            messages = [json.loads(r[0]) for r in rows]
            if messages:
                logger.info(f"Loaded {len(messages)} messages for thread {thread_id}")
            return messages
        except Exception as e:
            logger.error(f"ThreadStore.load failed for {thread_id}: {e}")
            return []

    def save(self, thread_id: str, messages: List[Dict[str, Any]]) -> None:
        """Persist the full message list for a thread (upsert by position)."""
        if self._conn is None:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            # Replace all messages for this thread
            self._conn.execute(
                "DELETE FROM messages WHERE thread_id = ?", (thread_id,)
            )
            self._conn.executemany(
                "INSERT INTO messages (thread_id, seq, message, created_at) VALUES (?, ?, ?, ?)",
                [
                    (thread_id, seq, json.dumps(msg), now)
                    for seq, msg in enumerate(messages)
                ],
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO thread_meta (thread_id, updated_at) VALUES (?, ?)",
                (thread_id, now),
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"ThreadStore.save failed for {thread_id}: {e}")

    def list_threads(self) -> List[Dict[str, str]]:
        """Return all thread IDs with their last-updated timestamps."""
        if self._conn is None:
            return []
        try:
            rows = self._conn.execute(
                "SELECT thread_id, updated_at FROM thread_meta ORDER BY updated_at DESC"
            ).fetchall()
            return [{"thread_id": r[0], "updated_at": r[1]} for r in rows]
        except Exception as e:
            logger.error(f"ThreadStore.list_threads failed: {e}")
            return []

    def delete(self, thread_id: str) -> None:
        """Delete all messages for a thread."""
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
            self._conn.execute("DELETE FROM thread_meta WHERE thread_id = ?", (thread_id,))
            self._conn.commit()
            logger.info(f"Deleted thread {thread_id}")
        except Exception as e:
            logger.error(f"ThreadStore.delete failed for {thread_id}: {e}")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
