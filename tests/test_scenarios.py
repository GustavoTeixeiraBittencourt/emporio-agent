"""Pins the exact facts used by examples/*.md (scripts/record_scenarios.py).

If the dataset changes, this is the test that should fail first -- before
anyone notices the example transcripts no longer match reality.
"""

from emporio_agent.rules import payment_options


def test_scenario_1_guitars_under_1000(catalog):
    result = catalog.search(category="Violões", max_price=1000)
    assert len(result["available"]) == 12
    electric = catalog.search(category="Violões", max_price=1000, electric=True)
    assert [p["product_id"] for p in electric["available"]] == ["107"]
    assert electric["available"][0]["name"].startswith("Shelby SGD-195E")
    assert electric["available"][0]["price_brl"] == 799.0


def test_scenario_2_takamine_gd20_price_and_expired_promo(catalog):
    gd20 = catalog.get("95")
    assert gd20.price_brl == 2199.0
    assert gd20.active_discount_percent is None
    r = payment_options(gd20.effective_price)
    assert r["max_installments"] == 12


def test_scenario_3_sunday_closed_and_dourados_not_local(catalog, orderbook):
    from datetime import datetime

    from emporio_agent import config
    from emporio_agent.rules import shipping_info, store_status

    sunday = datetime(2026, 3, 22, 15, 0, tzinfo=config.TIMEZONE)
    assert store_status(sunday)["is_open"] is False

    r = shipping_info("Dourados", order_total=1000.0)
    assert r["zone"] == "other"
    assert "fee_brl" not in r


def test_scenario_4_order_7_leticia_withdrawal_expired(orderbook):
    order = orderbook.verify("7", "leticia.rocha@jmail.com")
    assert order is not None
    summary = orderbook.order_summary(order)
    assert summary["total_brl"] == 159.9
    assert summary["order_date"] == "2026-02-03"


def test_scenario_5_order_8_anacarol_overdue(orderbook):
    order = orderbook.verify("8", "anacarol.ferreira@coldmail.com")
    assert order is not None
    summary = orderbook.order_summary(order)
    assert "overdue_shipment" in summary["flags"]


def test_scenario_5_martin_d28_price_for_manager_override_attempt(catalog):
    martin = catalog.get("93")
    assert martin.name.startswith("Martin D-28")
    assert martin.price_brl == 11499.0
    assert martin.active_discount_percent is None
