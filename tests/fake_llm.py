"""A scripted fake standing in for the OpenAI client in agent tests.

Mirrors just enough of the `openai` SDK's response shape
(`.choices[0].message.content` / `.tool_calls[i].function.{name,arguments}`)
for agent.run_turn to drive the loop without any network access.
"""

from __future__ import annotations

import json
from types import SimpleNamespace


class _FakeCompletions:
    def __init__(self, client: "FakeLLMClient"):
        self._client = client

    def create(self, **kwargs):
        return self._client._next_response(kwargs)


class _FakeChat:
    def __init__(self, client: "FakeLLMClient"):
        self.completions = _FakeCompletions(client)


class FakeLLMClient:
    """`turns` is a list (one per expected user turn) of step lists. Each
    step is one of:
      - {"content": "final answer text"}
      - {"tool_calls": [(tool_name, args_dict), ...]}
      - {"error": "message"}  -- raises RuntimeError instead of responding
    """

    def __init__(self, turns: list[list[dict]]):
        self.turns = [list(t) for t in turns]
        self.turn_index = -1
        self.step_index = 0
        self.chat = _FakeChat(self)
        self.received_messages: list[list[dict]] = []

    def _next_response(self, kwargs: dict):
        self.received_messages.append(kwargs.get("messages"))
        if self.step_index == 0:
            self.turn_index += 1
        steps = self.turns[self.turn_index]
        step = steps[self.step_index]
        self.step_index += 1
        if self.step_index >= len(steps):
            self.step_index = 0

        if "error" in step:
            raise RuntimeError(step["error"])

        tool_calls = None
        if "tool_calls" in step:
            tool_calls = [
                SimpleNamespace(
                    id=f"call_{i}",
                    function=SimpleNamespace(name=name, arguments=json.dumps(args)),
                )
                for i, (name, args) in enumerate(step["tool_calls"])
            ]
        message = SimpleNamespace(content=step.get("content"), tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])
