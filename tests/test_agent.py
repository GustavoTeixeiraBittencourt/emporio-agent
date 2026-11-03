import json

import pytest

from emporio_agent import config
from emporio_agent.agent import FALLBACK_MESSAGE, run_turn
from emporio_agent.session import Session
from emporio_agent.tools import ToolContext

from .fake_llm import FakeLLMClient


def test_tool_trace_is_recorded(tool_context, tool_schemas):
    client = FakeLLMClient(
        [
            [
                {"tool_calls": [("search_products", {"query": "Takamine GD20"})]},
                {"content": "O Takamine GD20 custa R$2.199."},
            ]
        ]
    )
    turn = run_turn(tool_context.session, tool_context, client, tool_schemas, "quanto custa o Takamine GD20?")
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0]["name"] == "search_products"
    assert turn.answer == "O Takamine GD20 custa R$2.199."


def test_privacy_enforced_in_code_not_just_prompt(tool_context, tool_schemas):
    client = FakeLLMClient(
        [
            [
                {"tool_calls": [("lookup_order", {"order_id": "7", "contact": "leticia.rocha@jmail.com"})]},
                {"content": "Seu pedido 7 está entregue."},
            ]
        ]
    )
    run_turn(tool_context.session, tool_context, client, tool_schemas, "quero ver meu pedido 7")
    tool_result = tool_context.session.messages[2]
    assert tool_result["role"] == "tool"
    payload = json.loads(tool_result["content"])
    assert "email" not in payload
    assert "phone" not in payload
    assert "leticia.rocha@jmail.com" not in tool_result["content"]


def test_escalation_is_recorded_to_handoffs_file(tool_context, tool_schemas):
    client = FakeLLMClient(
        [
            [
                {"tool_calls": [("escalate_to_human", {"reason": "cliente insatisfeito"})]},
                {"content": "Encaminhei para a equipe."},
            ]
        ]
    )
    run_turn(tool_context.session, tool_context, client, tool_schemas, "quero reclamar")
    assert config.HANDOFFS_PATH.exists()
    lines = config.HANDOFFS_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["reason"] == "cliente insatisfeito"
    assert entry["session_id"] == tool_context.session.session_id


def test_unknown_tool_and_invalid_args_do_not_crash_the_loop(tool_context, tool_schemas):
    client = FakeLLMClient(
        [
            [
                {"tool_calls": [("not_a_real_tool", {})]},
                {"content": "Desculpa, deixa eu tentar de outra forma."},
            ]
        ]
    )
    turn = run_turn(tool_context.session, tool_context, client, tool_schemas, "oi")
    assert turn.tool_calls[0]["result"]["error"].startswith("ferramenta desconhecida")
    assert turn.answer == "Desculpa, deixa eu tentar de outra forma."


def test_infinite_tool_loop_falls_back(tool_context, tool_schemas):
    client = FakeLLMClient(
        [[{"tool_calls": [("search_policies", {"query": "horário"})]}] * config.MAX_TOOL_ROUNDS]
    )
    turn = run_turn(tool_context.session, tool_context, client, tool_schemas, "oi")
    assert turn.answer == FALLBACK_MESSAGE
    assert len(turn.tool_calls) == config.MAX_TOOL_ROUNDS


def test_api_failure_rolls_back_the_whole_turn(tool_context, tool_schemas):
    client = FakeLLMClient([[{"error": "boom"}]])
    assert tool_context.session.messages == []
    with pytest.raises(RuntimeError):
        run_turn(tool_context.session, tool_context, client, tool_schemas, "oi")
    assert tool_context.session.messages == []


def test_session_persists_and_resumes(tool_context, tool_schemas):
    client = FakeLLMClient([[{"content": "Olá! Como posso ajudar?"}]])
    run_turn(tool_context.session, tool_context, client, tool_schemas, "oi")
    session_id = tool_context.session.session_id

    reloaded = Session.load_or_create(session_id)
    assert reloaded.messages == tool_context.session.messages
    assert reloaded.messages[0] == {"role": "user", "content": "oi"}


def test_history_window_never_starts_mid_tool_pair():
    session = Session("windowed")
    session.messages = [
        {"role": "user", "content": "primeira pergunta"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_0", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_0", "content": "{}"},
        {"role": "assistant", "content": "resposta 1"},
        {"role": "user", "content": "segunda pergunta"},
        {"role": "assistant", "content": "resposta 2"},
    ]
    window = session.history_window(3)
    assert window[0]["role"] == "user"
    assert window[0]["content"] == "segunda pergunta"


def test_history_window_keeps_everything_when_under_limit():
    session = Session("short")
    session.messages = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    assert session.history_window(40) == session.messages


def test_system_prompt_reflects_open_state(monkeypatch):
    from emporio_agent.prompt import build_system_prompt

    monkeypatch.setenv("AGENT_NOW", "2026-03-23T10:30:00")  # Monday, 10:30 -> open
    assert "ABERTA agora" in build_system_prompt()

    monkeypatch.setenv("AGENT_NOW", "2026-03-22T10:30:00")  # Sunday -> closed
    assert "FECHADA agora" in build_system_prompt()
