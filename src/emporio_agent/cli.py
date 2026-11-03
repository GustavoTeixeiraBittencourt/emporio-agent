"""Command-line interface: python -m emporio_agent [--session ID] [--debug]."""

from __future__ import annotations

import argparse
import sys
import uuid

from openai import OpenAI

from . import config
from .agent import run_turn
from .data import Catalog, OrderBook
from .policies import PolicyIndex
from .session import Session
from .tools import ToolContext, build_tool_schemas

EXIT_COMMANDS = {"/sair", "/exit", "/quit"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emporio_agent")
    parser.add_argument("--session", dest="session_id", default=None, help="Retoma uma sessão existente pelo ID.")
    parser.add_argument("--debug", action="store_true", help="Mostra as chamadas de ferramentas.")
    args = parser.parse_args(argv)

    # Windows consoles default to cp1252 and choke on characters like U+202F.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if not config.LLM_API_KEY:
        print(
            "LLM_API_KEY não configurada. Copie .env.example para .env e "
            "preencha a chave (veja o README para provedores gratuitos)."
        )
        return 1

    catalog = Catalog()
    orderbook = OrderBook(catalog=catalog)
    policy_index = PolicyIndex()
    tool_schemas = build_tool_schemas(catalog)

    session_id = args.session_id or uuid.uuid4().hex[:8]
    session = Session.load_or_create(session_id)
    ctx = ToolContext(catalog=catalog, orderbook=orderbook, policy_index=policy_index, session=session)

    client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)

    print(f"Tom -- Empório da Música (sessão: {session_id}). Digite /sair para encerrar.\n")
    while True:
        try:
            user_text = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_text:
            continue
        if user_text.lower() in EXIT_COMMANDS:
            break

        try:
            turn = run_turn(session, ctx, client, tool_schemas, user_text)
        except Exception as exc:  # noqa: BLE001 -- keep the chat alive on API errors
            print(f"[erro ao falar com o modelo, tente de novo: {exc}]\n")
            continue

        if args.debug:
            for call in turn.tool_calls:
                print(f"  [tool] {call['name']}({call['arguments']}) -> {call['result']}")
        print(f"Tom: {turn.answer}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
