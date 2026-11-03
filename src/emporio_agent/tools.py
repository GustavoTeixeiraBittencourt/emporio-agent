"""The agent's seven tools: OpenAI-format schemas + dispatch.

Design principle (see README): the LLM only ever decides *when* to call a
tool. Every tool handler here is plain, deterministic Python that decides
*what is allowed* -- prices, stock, verification, dates -- and the model
never sees a fact it didn't get from one of these functions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from . import config
from .data import Catalog, OrderBook
from .policies import PolicyIndex
from .rules import ReturnableOrder, payment_options, return_check, shipping_info

if TYPE_CHECKING:  # avoid a runtime import cycle with session.py
    from .session import Session


@dataclass
class ToolContext:
    catalog: Catalog
    orderbook: OrderBook
    policy_index: PolicyIndex
    session: "Session"


def build_tool_schemas(catalog: Catalog) -> list[dict]:
    category_names = catalog.list_category_names()
    return [
        {
            "type": "function",
            "function": {
                "name": "search_products",
                "description": (
                    "Busca instrumentos no catálogo da loja por nome/marca/modelo, "
                    "categoria e faixa de preço. Use antes de informar preço, "
                    "disponibilidade ou características de qualquer produto -- "
                    "nunca confie em conhecimento próprio sobre o catálogo."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Texto livre de marca/modelo, ex.: 'Takamine GD20'.",
                        },
                        "category": {
                            "type": "string",
                            "enum": category_names,
                            "description": "Categoria exata do catálogo, se o cliente mencionar uma.",
                        },
                        "max_price": {
                            "type": "number",
                            "description": "Preço máximo (preço já com promoção aplicada, se houver).",
                        },
                        "min_price": {"type": "number", "description": "Preço mínimo."},
                        "strings": {
                            "type": "string",
                            "enum": ["nylon", "steel"],
                            "description": "Material das cordas, para violões/ukuleles.",
                        },
                        "electric": {
                            "type": "boolean",
                            "description": "true = eletroacústico (com captador); false = acústico puro.",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_payment_options",
                "description": (
                    "Calcula as formas e condições de pagamento (PIX, débito, "
                    "boleto, parcelamento no crédito) para um produto específico "
                    "do catálogo. Nunca calcule parcelas ou descontos de cabeça."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "ID do produto (retornado por search_products).",
                        }
                    },
                    "required": ["product_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": (
                    "Busca um pedido pelo número, exigindo também um contato "
                    "(e-mail ou telefone) para confirmar que quem está falando é "
                    "o dono do pedido. Nunca aceite identificação só pelo nome. "
                    "Use antes de falar qualquer detalhe de um pedido específico."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Número do pedido."},
                        "contact": {
                            "type": "string",
                            "description": "E-mail ou telefone informado pelo cliente.",
                        },
                    },
                    "required": ["order_id", "contact"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_return_eligibility",
                "description": (
                    "Avalia se um pedido já verificado (via lookup_order na mesma "
                    "conversa) é elegível para devolução/troca, aplicando as "
                    "regras do manual (arrependimento, defeito ou preferência). "
                    "Nunca decida isso sozinho; sempre chame esta ferramenta."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Número do pedido (já verificado)."},
                        "reason": {
                            "type": "string",
                            "enum": ["arrependimento", "defeito", "preferencia"],
                            "description": (
                                "arrependimento = compra online sem defeito, "
                                "'me arrependi'; defeito = problema de "
                                "fabricação; preferencia = troca por cor/modelo/tamanho."
                            ),
                        },
                        "received_on": {
                            "type": "string",
                            "description": "Data real de recebimento informada pelo cliente, formato AAAA-MM-DD, se souber.",
                        },
                        "is_online_purchase": {
                            "type": "boolean",
                            "description": "true se a compra foi feita online/remota, false se foi na loja física.",
                        },
                    },
                    "required": ["order_id", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_policies",
                "description": (
                    "Busca no manual interno de políticas (trocas, devoluções, "
                    "formas de pagamento, frete, garantia, privacidade). Use "
                    "sempre que a pergunta for sobre uma regra da loja, não sobre "
                    "um produto ou pedido específico."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "O que o cliente quer saber."}
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_shipping_info",
                "description": (
                    "Calcula prazo e custo de entrega para uma cidade, dado o "
                    "total do pedido e (se possível) os nomes dos produtos, já "
                    "que itens grandes (bateria acústica, piano, contrabaixo) "
                    "exigem cotação individual."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "Cidade de destino."},
                        "order_total": {
                            "type": "number",
                            "description": "Valor total do pedido, para checar frete grátis.",
                        },
                        "product_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Nomes dos produtos do pedido, se conhecidos.",
                        },
                    },
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "escalate_to_human",
                "description": (
                    "Registra o atendimento para um humano assumir: reclamações, "
                    "pedidos com inconsistência de dados, casos de garantia entre "
                    "30 e 90 dias, ou qualquer situação fora do que você pode "
                    "resolver com as outras ferramentas."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Resumo do motivo do encaminhamento."},
                        "order_id": {"type": "string", "description": "Número do pedido relacionado, se houver."},
                        "contact": {"type": "string", "description": "Contato do cliente, se disponível."},
                    },
                    "required": ["reason"],
                },
            },
        },
    ]


def _search_products(ctx: ToolContext, args: dict) -> dict:
    return ctx.catalog.search(
        query=args.get("query"),
        category=args.get("category"),
        max_price=args.get("max_price"),
        min_price=args.get("min_price"),
        strings=args.get("strings"),
        electric=args.get("electric"),
    )


def _get_payment_options(ctx: ToolContext, args: dict) -> dict:
    product_id = str(args.get("product_id") or "").strip()
    product = ctx.catalog.get(product_id)
    if product is None:
        return {"error": "produto não encontrado"}
    if not product.is_buyable:
        return {
            "error": "este produto não está disponível para compra no momento",
            "availability": product.availability,
        }
    return payment_options(product.effective_price, promotional=bool(product.active_discount_percent))


def _lookup_order(ctx: ToolContext, args: dict) -> dict:
    order_id = str(args.get("order_id") or "").strip()
    contact = str(args.get("contact") or "").strip()
    order = ctx.orderbook.verify(order_id, contact)
    if order is None:
        return {"error": "não encontrei esse pedido com esse contato. Confira o número do pedido e o e-mail/telefone."}
    ctx.session.verify_order(order_id)
    return ctx.orderbook.order_summary(order)


def _check_return_eligibility(ctx: ToolContext, args: dict) -> dict:
    order_id = str(args.get("order_id") or "").strip()
    if not ctx.session.is_order_verified(order_id):
        return {"error": "esse pedido ainda não foi verificado nesta conversa. Chame lookup_order primeiro."}
    order = ctx.orderbook.orders.get(order_id)
    if order is None:
        return {"error": "pedido não encontrado"}

    received_on = None
    raw_received = args.get("received_on")
    if raw_received:
        try:
            received_on = datetime.strptime(raw_received, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "received_on inválido, use o formato AAAA-MM-DD"}

    reasonable_order = ReturnableOrder(
        status=order.status, order_date=order.order_date, estimated_delivery=order.estimated_delivery
    )
    return return_check(
        reasonable_order,
        reason=str(args.get("reason") or ""),
        today=config.now().date(),
        received_on=received_on,
        is_online_purchase=args.get("is_online_purchase"),
    )


def _search_policies(ctx: ToolContext, args: dict) -> dict:
    query = str(args.get("query") or "")
    results = ctx.policy_index.search(query)
    if not results:
        return {"results": [], "message": "não encontrei nada sobre isso no manual de políticas"}
    return {"results": results}


def _get_shipping_info(ctx: ToolContext, args: dict) -> dict:
    return shipping_info(
        city=str(args.get("city") or ""),
        order_total=args.get("order_total"),
        product_names=args.get("product_names"),
    )


def _escalate_to_human(ctx: ToolContext, args: dict) -> dict:
    entry = {
        "timestamp": config.now().isoformat(),
        "session_id": ctx.session.session_id,
        "reason": args.get("reason"),
        "order_id": args.get("order_id"),
        "contact": args.get("contact"),
    }
    config.HANDOFFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.HANDOFFS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"status": "escalated", "message": "Encaminhado para a equipe. Retorno em até 24 horas úteis."}


_HANDLERS: dict[str, Callable[[ToolContext, dict], dict]] = {
    "search_products": _search_products,
    "get_payment_options": _get_payment_options,
    "lookup_order": _lookup_order,
    "check_return_eligibility": _check_return_eligibility,
    "search_policies": _search_policies,
    "get_shipping_info": _get_shipping_info,
    "escalate_to_human": _escalate_to_human,
}


def run_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict:
    """Execute a tool call, never raising -- invalid args, unknown tool
    names, and internal errors all come back as a JSON-able error dict so
    the agent loop can keep going."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"ferramenta desconhecida: {name}"}
    try:
        return handler(ctx, arguments or {})
    except Exception as exc:  # noqa: BLE001
        return {"error": f"erro ao executar '{name}': {exc}"}
