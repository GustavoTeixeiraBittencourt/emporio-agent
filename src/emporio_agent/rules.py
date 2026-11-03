"""Deterministic business rules: store hours, payments, shipping, returns.

None of this is left to the LLM's judgement -- it is exactly the kind of
arithmetic/calendar logic that language models get subtly wrong, and the
brief is explicit that prices/stock/deadlines must never be asserted
without consulting "the system". These functions *are* the system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import holidays

from . import config
from .data import fold

_HOLIDAYS = holidays.Brazil(subdiv="MS")

_WEEKDAY_OPEN, _WEEKDAY_CLOSE = time(9, 0), time(18, 0)
_SATURDAY_OPEN, _SATURDAY_CLOSE = time(9, 0), time(13, 0)


def _day_hours(d: date) -> tuple[time, time] | None:
    """Open/close time for a given date, or None if closed all day."""
    if d.weekday() == 6 or d in _HOLIDAYS:  # Sunday or holiday
        return None
    if d.weekday() == 5:  # Saturday
        return _SATURDAY_OPEN, _SATURDAY_CLOSE
    return _WEEKDAY_OPEN, _WEEKDAY_CLOSE


def store_status(now: datetime | None = None) -> dict:
    now = now or config.now()
    d, t = now.date(), now.time()
    hours = _day_hours(d)

    is_open = hours is not None and hours[0] <= t < hours[1]

    next_open = None
    if not is_open:
        if hours is not None and t < hours[0]:
            next_open = datetime.combine(d, hours[0], tzinfo=now.tzinfo)
        else:
            for step in range(1, 15):
                cd = d + timedelta(days=step)
                cd_hours = _day_hours(cd)
                if cd_hours is not None:
                    next_open = datetime.combine(cd, cd_hours[0], tzinfo=now.tzinfo)
                    break

    return {
        "is_open": is_open,
        "checked_at": now.isoformat(),
        "next_open": next_open.isoformat() if next_open else None,
    }


def _installment_minimum(n: int) -> float:
    if n <= 3:
        return 50.0
    if n <= 6:
        return 80.0
    return 100.0  # 7..12, per manual section 3.1


def payment_options(price_brl: float, promotional: bool = False) -> dict:
    """`price_brl` is the price the customer would actually pay (i.e. the
    effective/promotional price if one applies). `promotional` says whether
    that price already reflects an active promotion, since PIX's 5% does
    not stack on top of a promotion (manual section 6.2)."""
    pix_price = price_brl if promotional else round(price_brl * 0.95, 2)

    installments = []
    max_installments = 0
    for n in range(1, 13):
        installment_value = round(price_brl / n, 2)
        eligible = n == 1 or installment_value >= _installment_minimum(n)
        if eligible:
            max_installments = n
        installments.append(
            {"n": n, "installment_value_brl": installment_value, "eligible": eligible}
        )

    return {
        "pix": {"price_brl": pix_price, "discount_applied": not promotional},
        "debit": {"price_brl": price_brl},
        "boleto": {"price_brl": price_brl, "settlement_business_days": 3},
        "credit_installments": installments,
        "max_installments": max_installments,
        "combined_payment_allowed": price_brl > 2000,
    }


_BULKY_KEYWORDS = ("bateria acustica", "piano", "contrabaixo")


def shipping_info(
    city: str, order_total: float | None = None, product_names: list[str] | None = None
) -> dict:
    product_names = product_names or []
    needs_quote = any(
        any(k in fold(name) for k in _BULKY_KEYWORDS) for name in product_names
    )
    is_local = fold(city) == "campo grande"

    if needs_quote:
        zone = "local" if is_local else "other"
        return {
            "zone": zone,
            "needs_individual_quote": True,
            "note": "Instrumentos de grande porte (bateria acústica, piano, contrabaixo) exigem frete especial com cotação individual.",
        }

    if is_local:
        free = order_total is not None and order_total > 500
        return {
            "zone": "local",
            "free_shipping": free,
            "fee_brl": 0.0 if free else 35.0,
            "eta_business_days": "1 a 3",
            "carrier": "motoboy próprio",
        }

    return {
        "zone": "other",
        "needs_individual_quote": False,
        "note": "O valor exato do frete é calculado pelo CEP de destino, peso e dimensões do produto -- não temos uma tabela fixa de preço aqui.",
        "options": [
            {"carrier": "Correios PAC", "eta_business_days": "5 a 12", "insured": True},
            {"carrier": "Correios SEDEX", "eta_business_days": "2 a 5", "insured": True},
            {"carrier": "Jadlog", "eta_business_days": "3 a 8", "insured": True},
        ],
    }


@dataclass
class ReturnableOrder:
    """Minimal view of an order that return_check() needs."""

    status: str
    order_date: date | None
    estimated_delivery: date | None


def return_check(
    order: ReturnableOrder,
    reason: str,
    today: date,
    received_on: date | None = None,
    is_online_purchase: bool | None = None,
) -> dict:
    if order.status in ("pending", "confirmed"):
        return {
            "eligible": False,
            "path": "not_delivered_yet",
            "escalate": True,
            "message": "O pedido ainda não foi entregue, então não é possível avaliar devolução agora.",
        }
    if order.status == "shipped":
        return {
            "eligible": False,
            "path": "in_transit",
            "escalate": False,
            "message": "O pedido ainda está em trânsito. Assim que for recebido, dá pra reavaliar a devolução.",
        }
    if order.status == "cancelled":
        return {
            "eligible": False,
            "path": "cancelled",
            "escalate": False,
            "message": "Esse pedido já está cancelado, não há compra entregue para devolver.",
        }
    if order.status != "delivered":
        return {
            "eligible": None,
            "path": "unknown_status",
            "escalate": True,
            "message": "Status de pedido não reconhecido para fins de devolução.",
        }

    received_is_estimate = received_on is None
    effective_received = received_on or order.estimated_delivery
    assumed_online = is_online_purchase is None
    online = True if is_online_purchase is None else is_online_purchase

    if reason == "arrependimento":
        if not online:
            return {
                "eligible": False,
                "path": "not_online",
                "escalate": False,
                "message": "O direito de arrependimento (7 dias) vale só para compras feitas online.",
            }
        if effective_received is None:
            return {
                "eligible": None,
                "path": "missing_date",
                "escalate": False,
                "message": "Preciso da data em que o produto foi recebido para calcular o prazo.",
            }
        days_since = (today - effective_received).days
        margin = 7 - days_since
        eligible = days_since <= 7
        return {
            "eligible": eligible,
            "path": "right_of_withdrawal",
            "window_days": 7,
            "days_since_received": days_since,
            "received_date_is_estimate": received_is_estimate,
            "assumed_online_purchase": assumed_online,
            "confidence": "low" if received_is_estimate and abs(margin) <= 3 else "high",
            "escalate": False,
            "message": (
                "Dentro do prazo de 7 dias corridos: reembolso na mesma forma de pagamento em até 10 dias úteis, frete de volta por conta da loja."
                if eligible
                else "O prazo de 7 dias corridos para arrependimento já passou."
            ),
        }

    if reason == "preferencia":
        if effective_received is None:
            return {
                "eligible": None,
                "path": "missing_date",
                "escalate": False,
                "message": "Preciso da data em que o produto foi recebido para calcular o prazo.",
            }
        days_since = (today - effective_received).days
        margin = 7 - days_since
        eligible = days_since <= 7
        return {
            "eligible": eligible,
            "path": "preference_exchange",
            "window_days": 7,
            "days_since_received": days_since,
            "received_date_is_estimate": received_is_estimate,
            "confidence": "low" if received_is_estimate and abs(margin) <= 3 else "high",
            "escalate": False,
            "message": (
                "Dentro do prazo de 7 dias para troca por preferência, sujeita à disponibilidade do produto desejado."
                if eligible
                else "O prazo de 7 dias para troca por preferência já passou."
            ),
        }

    if reason == "defeito":
        if order.order_date is None:
            return {
                "eligible": None,
                "path": "missing_date",
                "escalate": True,
                "message": "Não há data de compra registrada; preciso encaminhar para a equipe.",
            }
        days_since_purchase = (today - order.order_date).days
        if days_since_purchase <= 30:
            return {
                "eligible": True,
                "path": "manufacturing_defect_exchange",
                "days_since_purchase": days_since_purchase,
                "escalate": False,
                "message": "Dentro de 30 dias da compra: troca por defeito de fabricação.",
            }
        if effective_received is None:
            return {
                "eligible": None,
                "path": "missing_date",
                "escalate": True,
                "message": "Preciso da data de recebimento para avaliar a garantia; vou encaminhar para a equipe.",
            }
        days_since_received = (today - effective_received).days
        if days_since_received <= 90:
            return {
                "eligible": None,
                "path": "warranty_gray_zone",
                "days_since_purchase": days_since_purchase,
                "days_since_received": days_since_received,
                "received_date_is_estimate": received_is_estimate,
                "escalate": True,
                "message": "Fora do prazo padrão de troca da loja (30 dias), mas dentro da garantia legal de 90 dias -- precisa de avaliação da equipe.",
            }
        return {
            "eligible": False,
            "path": "manufacturer_warranty",
            "days_since_purchase": days_since_purchase,
            "days_since_received": days_since_received,
            "received_date_is_estimate": received_is_estimate,
            "escalate": False,
            "message": "Mais de 90 dias desde o recebimento: a garantia agora é do fabricante. A loja pode intermediar o contato, se precisar.",
        }

    return {
        "eligible": None,
        "path": "unknown_reason",
        "escalate": True,
        "message": "Não reconheci esse motivo de devolução; vou encaminhar para a equipe.",
    }
