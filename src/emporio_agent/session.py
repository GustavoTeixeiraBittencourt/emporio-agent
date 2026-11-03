"""Per-conversation persistence: one JSON file per session id.

Each turn is appended and saved immediately, so a conversation can be
resumed later with `--session ID`. Only the last N messages are ever sent
to the model (see history_window); the full history always stays on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: list[dict] = []
        self.verified_orders: set[str] = set()
        self.path: Path = config.SESSIONS_DIR / f"{session_id}.json"

    @classmethod
    def load_or_create(cls, session_id: str) -> "Session":
        session = cls(session_id)
        if session.path.exists():
            data = json.loads(session.path.read_text(encoding="utf-8"))
            session.messages = data.get("messages", [])
            session.verified_orders = set(data.get("verified_orders", []))
        return session

    def verify_order(self, order_id: str) -> None:
        self.verified_orders.add(str(order_id))

    def is_order_verified(self, order_id: str) -> bool:
        return str(order_id) in self.verified_orders

    def history_window(self, limit: int) -> list[dict]:
        """Last `limit` messages, moved forward to the next 'user' message
        so the window never starts mid-way through an assistant
        tool_calls/tool pair."""
        if len(self.messages) <= limit:
            return list(self.messages)
        start = len(self.messages) - limit
        while start < len(self.messages) and self.messages[start].get("role") != "user":
            start += 1
        if start >= len(self.messages):
            start = len(self.messages) - limit
        return self.messages[start:]

    def save(self) -> None:
        config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": self.session_id,
            "messages": self.messages,
            "verified_orders": sorted(self.verified_orders),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
