"""Runtime configuration: paths, timezone, and the freezable clock."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TIMEZONE = ZoneInfo("America/Campo_Grande")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.environ.get("EMPORIO_DATA_DIR", PROJECT_ROOT / "data"))
SESSIONS_DIR = Path(os.environ.get("EMPORIO_SESSIONS_DIR", PROJECT_ROOT / ".sessions"))
HANDOFFS_PATH = Path(os.environ.get("EMPORIO_HANDOFFS_PATH", PROJECT_ROOT / "handoffs.jsonl"))

LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = 0.3

MAX_TOOL_ROUNDS = 6
HISTORY_WINDOW = 40
MAX_USER_MESSAGE_CHARS = 2000


def now() -> datetime:
    """Current time in the store's timezone.

    Reads AGENT_NOW (ISO 8601, naive or aware) at call time rather than at
    import time, so tests and the scenario recorder can freeze/unfreeze the
    clock per-case via monkeypatch/env without reloading the module.
    """
    frozen = os.environ.get("AGENT_NOW")
    if frozen:
        dt = datetime.fromisoformat(frozen)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        return dt.astimezone(TIMEZONE)
    return datetime.now(TIMEZONE)
