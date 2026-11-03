import importlib
from pathlib import Path

import pytest

from emporio_agent import config
from emporio_agent.data import Catalog, OrderBook
from emporio_agent.policies import PolicyIndex
from emporio_agent.session import Session
from emporio_agent.tools import ToolContext, build_tool_schemas

FROZEN_NOW = "2026-03-23T10:30:00"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setenv("AGENT_NOW", FROZEN_NOW)
    yield


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    sessions_dir = tmp_path / ".sessions"
    handoffs_path = tmp_path / "handoffs.jsonl"
    monkeypatch.setattr(config, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(config, "HANDOFFS_PATH", handoffs_path)
    yield


@pytest.fixture
def catalog() -> Catalog:
    return Catalog()


@pytest.fixture
def orderbook(catalog) -> OrderBook:
    return OrderBook(catalog=catalog)


@pytest.fixture
def policy_index() -> PolicyIndex:
    return PolicyIndex()


@pytest.fixture
def session() -> Session:
    return Session("test-session")


@pytest.fixture
def tool_context(catalog, orderbook, policy_index, session) -> ToolContext:
    return ToolContext(catalog=catalog, orderbook=orderbook, policy_index=policy_index, session=session)


@pytest.fixture
def tool_schemas(catalog):
    return build_tool_schemas(catalog)
