"""
Advisory Board (Blackboard Architecture)
SQLite-backed Advisory Board with in-memory caching.
Exposes board tools for agents using Microsoft Agent Framework (@tool decorator).

Verified API:
- agent_framework.tool
  Verified from official microsoft/agent-framework repository:
  python/packages/core/agent_framework/_tools.py
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from threading import RLock

from agent_framework import tool  # [VERIFIED: agent-framework v1.25.0]
from board.models import AdvisoryBoardEntry, BoardState


class AdvisoryBoard:
    """
    SQLite-backed Blackboard with an in-memory session cache.
    Thread-safe implementation for multi-agent asynchronous workflows.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = RLock()
        # In-memory cache: session_id -> { "entries": [AdvisoryBoardEntry], "state": BoardState }
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        set_advisory_board(self)

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            # Table for blackboard entries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    data_freshness TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_session ON entries (session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_type ON entries (session_id, type)")

            # Table for blackboard session states
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_states (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            self._conn.commit()

    def post_entry(
        self,
        session_id: str,
        agent_name: str,
        type: str,
        payload: Dict[str, Any],
        confidence: float,
        data_freshness: str,
        sources: List[str],
        status: str = "SUCCESS",
        version: int = 1,
    ) -> AdvisoryBoardEntry:
        """
        Posts a new entry to the advisory board, persisting to SQLite and updating in-memory cache.
        """
        entry_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        entry = AdvisoryBoardEntry(
            entry_id=entry_id,
            session_id=session_id,
            agent_name=agent_name,
            type=type,
            payload=payload,
            confidence=max(0.0, min(1.0, float(confidence))),
            data_freshness=data_freshness,
            sources=sources,
            timestamp=now_iso,
            status=status,
            version=version,
        )

        with self._lock:
            # 1. Persist to SQLite
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO entries (
                        entry_id, session_id, agent_name, type, payload,
                        confidence, data_freshness, sources, timestamp, status, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.session_id,
                        entry.agent_name,
                        entry.type,
                        json.dumps(entry.payload),
                        entry.confidence,
                        entry.data_freshness,
                        json.dumps(entry.sources),
                        entry.timestamp,
                        entry.status,
                        entry.version,
                    ),
                )
                conn.commit()

            # 2. Update in-memory cache
            if session_id not in self._cache:
                self._cache[session_id] = {"entries": [], "state": BoardState.CREATED.value}
            self._cache[session_id]["entries"].append(entry)

        return entry

    def get_entries(self, session_id: str, entry_type: Optional[str] = None) -> List[AdvisoryBoardEntry]:
        """
        Retrieves entries for a given session, optionally filtered by entry type.
        Uses in-memory cache if available; otherwise falls back to SQLite.
        """
        with self._lock:
            if session_id in self._cache:
                entries = self._cache[session_id]["entries"]
                if entry_type:
                    return [e for e in entries if e.type == entry_type]
                return list(entries)

            # Fallback to SQLite if not in cache
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if entry_type:
                    cursor.execute(
                        "SELECT * FROM entries WHERE session_id = ? AND type = ? ORDER BY timestamp ASC",
                        (session_id, entry_type),
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM entries WHERE session_id = ? ORDER BY timestamp ASC",
                        (session_id,),
                    )
                rows = cursor.fetchall()

            entries = []
            for row in rows:
                entries.append(
                    AdvisoryBoardEntry(
                        entry_id=row["entry_id"],
                        session_id=row["session_id"],
                        agent_name=row["agent_name"],
                        type=row["type"],
                        payload=json.loads(row["payload"]),
                        confidence=row["confidence"],
                        data_freshness=row["data_freshness"],
                        sources=json.loads(row["sources"]),
                        timestamp=row["timestamp"],
                        status=row["status"],
                        version=row["version"],
                    )
                )

            # Populate cache
            if session_id not in self._cache:
                self._cache[session_id] = {"entries": entries, "state": self.get_state(session_id)}
            else:
                self._cache[session_id]["entries"] = entries

            return entries

    def get_entry(self, session_id: str, entry_type: str) -> Optional[AdvisoryBoardEntry]:
        """
        Retrieves the latest entry of a specific type for the session.
        """
        entries = self.get_entries(session_id=session_id, entry_type=entry_type)
        return entries[-1] if entries else None

    def get_state(self, session_id: str) -> str:
        """
        Retrieves the current state of the advisory board for the session.
        """
        with self._lock:
            if session_id in self._cache and "state" in self._cache[session_id]:
                return self._cache[session_id]["state"]

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT state FROM session_states WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                if row:
                    state = row["state"]
                else:
                    state = BoardState.CREATED.value

            if session_id not in self._cache:
                self._cache[session_id] = {"entries": [], "state": state}
            else:
                self._cache[session_id]["state"] = state
            return state

    def set_state(self, session_id: str, state: str) -> None:
        """
        Updates the state of the advisory board for the session.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO session_states (session_id, state, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at
                    """,
                    (session_id, state, now_iso),
                )
                conn.commit()

            if session_id not in self._cache:
                self._cache[session_id] = {"entries": [], "state": state}
            else:
                self._cache[session_id]["state"] = state


# Global singleton instance for framework tools
_global_board: Optional[AdvisoryBoard] = None


def get_advisory_board(db_path: str = "advisory_board.db") -> AdvisoryBoard:
    global _global_board
    if _global_board is None:
        _global_board = AdvisoryBoard(db_path=db_path)
    return _global_board


def set_advisory_board(board: AdvisoryBoard) -> None:
    global _global_board
    _global_board = board


# --- Microsoft Agent Framework Tools (@tool) ---

@tool(approval_mode="never_require")
def read_board_entry(session_id: str, entry_type: str) -> str:
    """
    Read the latest entry of a specific type (e.g. 'INTAKE', 'WEATHER', 'MARKET', 'CROP_ACTION', 'SCHEME')
    from the Advisory Board for the current session.

    Args:
        session_id: The session ID of the current advisory request.
        entry_type: The entry type string to read.

    Returns:
        JSON string containing the entry fields and payload, or empty object if not found.
    """
    board = get_advisory_board()
    entry = board.get_entry(session_id=session_id, entry_type=entry_type)
    if not entry:
        return json.dumps({"error": f"Entry type '{entry_type}' not found for session '{session_id}'"})
    return entry.model_dump_json()


@tool(approval_mode="never_require")
def read_all_board_entries(session_id: str) -> str:
    """
    Read all existing entries posted to the Advisory Board for the current session.

    Args:
        session_id: The session ID of the current advisory request.

    Returns:
        JSON array of all board entries with their payloads, timestamps, and confidence scores.
    """
    board = get_advisory_board()
    entries = board.get_entries(session_id=session_id)
    return json.dumps([e.model_dump() for e in entries])


@tool(approval_mode="never_require")
def post_board_entry(
    session_id: str,
    agent_name: str,
    entry_type: str,
    payload_json: str,
    confidence: float,
    data_freshness: str,
    sources_json: str,
) -> str:
    """
    Post a new verified entry to the shared Advisory Board.

    Args:
        session_id: Current session identifier.
        agent_name: Name of the agent posting the entry.
        entry_type: Category (INTAKE, WEATHER, CROP_ACTION, MARKET, SCHEME, ADVISORY, FAILED).
        payload_json: Serialized JSON object containing structured payload fields.
        confidence: Numerical score 0.0 to 1.0 indicating result reliability.
        data_freshness: Freshness status ('live', 'cached', 'stale', or 'unavailable').
        sources_json: JSON array of source references or API endpoints.

    Returns:
        JSON string confirming entry creation with its assigned entry_id.
    """
    board = get_advisory_board()
    try:
        payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        sources = json.loads(sources_json) if isinstance(sources_json, str) else sources_json
        entry = board.post_entry(
            session_id=session_id,
            agent_name=agent_name,
            type=entry_type,
            payload=payload,
            confidence=confidence,
            data_freshness=data_freshness,
            sources=sources,
        )
        return json.dumps({"status": "SUCCESS", "entry_id": entry.entry_id})
    except Exception as exc:
        return json.dumps({"status": "ERROR", "message": str(exc)})

