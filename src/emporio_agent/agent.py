"""The function-calling loop: model decides when to call tools, this
module executes them and feeds results back, up to a bounded number of
rounds."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import config
from .prompt import build_system_prompt
from .session import Session
from .tools import ToolContext, run_tool

FALLBACK_MESSAGE = (
    "Desculpa, não consegui concluir essa consulta agora. Pode tentar "
    "reformular ou, se preferir, encaminho para nossa equipe te ajudar."
)


@dataclass
class Turn:
    answer: str
    tool_calls: list[dict] = field(default_factory=list)


def _tool_call_entry(tc) -> dict:
    return {
        "id": tc.id,
        "type": "function",
        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
    }


def run_turn(session: Session, ctx: ToolContext, client, tool_schemas: list[dict], user_text: str) -> Turn:
    """Run one full user turn against the LLM, executing tool calls until
    a final answer arrives or MAX_TOOL_ROUNDS is hit.

    Only commits anything to `session` on success. If the API call raises,
    the exception propagates and the session is left exactly as it was
    before this call -- no half-finished tool_calls pair gets persisted.
    """
    user_text = (user_text or "")[: config.MAX_USER_MESSAGE_CHARS]
    context_messages = session.history_window(config.HISTORY_WINDOW)
    new_messages: list[dict] = [{"role": "user", "content": user_text}]
    tool_trace: list[dict] = []
    system_message = {"role": "system", "content": build_system_prompt()}

    answer = FALLBACK_MESSAGE
    for _round in range(config.MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            messages=[system_message] + context_messages + new_messages,
            tools=tool_schemas,
            tool_choice="auto",
        )
        message = response.choices[0].message

        assistant_entry: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_entry["tool_calls"] = [_tool_call_entry(tc) for tc in message.tool_calls]
        new_messages.append(assistant_entry)

        if not message.tool_calls:
            answer = message.content or ""
            break

        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
                result = {"error": "argumentos inválidos (JSON malformado)"}
            else:
                result = run_tool(tc.function.name, args, ctx)
            tool_trace.append({"name": tc.function.name, "arguments": args, "result": result})
            new_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    session.messages.extend(new_messages)
    session.save()
    return Turn(answer=answer, tool_calls=tool_trace)
