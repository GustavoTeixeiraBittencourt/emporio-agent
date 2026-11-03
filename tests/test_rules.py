from datetime import date, datetime

import pytest

from emporio_agent import config
from emporio_agent.rules import ReturnableOrder, payment_options, return_check, shipping_info, store_status

TZ = config.TIMEZONE


@pytest.mark.parametrize(
    "price,expected_max",
    [(2199, 12), (599.90, 6), (159.90, 3), (120, 2), (1000, 10)],
)
def test_installment_tiers(price, expected_max):
    assert payment_options(price)["max_installments"] == expected_max


def test_pix_discount_applies_only_without_promotion():
    r = payment_options(100.0, promotional=False)
    assert r["pix"]["price_brl"] == 95.0
    assert r["pix"]["discount_applied"] is True

    r_promo = payment_options(100.0, promotional=True)
    assert r_promo["pix"]["price_brl"] == 100.0
    assert r_promo["pix"]["discount_applied"] is False


def test_combined_payment_threshold():
    assert payment_options(2000.01)["combined_payment_allowed"] is True
    assert payment_options(2000.00)["combined_payment_allowed"] is False


def test_shipping_free_threshold_strictly_above_500():
    assert shipping_info("Campo Grande", order_total=500.00)["fee_brl"] == 35.0
    assert shipping_info("Campo Grande", order_total=500.01)["fee_brl"] == 0.0


def test_shipping_other_city_has_no_invented_price():
    r = shipping_info("Dourados", order_total=300.0)
    assert "fee_brl" not in r
    assert len(r["options"]) == 3


def test_shipping_bulky_item_needs_individual_quote():
    r = shipping_info("Campo Grande", order_total=5000.0, product_names=["Bateria Acústica Yamaha Kit 1 Studio"])
    assert r["needs_individual_quote"] is True


@pytest.mark.parametrize(
    "when,expected_open",
    [
        (datetime(2026, 3, 20, 17, 59, tzinfo=TZ), True),  # Friday, just before close
        (datetime(2026, 3, 20, 18, 0, tzinfo=TZ), False),  # Friday, exactly 18:00 -> closed
        (datetime(2026, 3, 21, 12, 59, tzinfo=TZ), True),  # Saturday
        (datetime(2026, 3, 21, 13, 0, tzinfo=TZ), False),  # Saturday, exactly 13:00 -> closed
        (datetime(2026, 3, 22, 10, 0, tzinfo=TZ), False),  # Sunday
        (datetime(2026, 9, 7, 10, 0, tzinfo=TZ), False),  # holiday: Independência do Brasil
    ],
)
def test_store_status_open_closed(when, expected_open):
    assert store_status(when)["is_open"] is expected_open


def test_store_status_next_open_after_sunday():
    status = store_status(datetime(2026, 3, 22, 10, 0, tzinfo=TZ))
    assert status["next_open"] == "2026-03-23T09:00:00-04:00"


ORDER_DELIVERED = ReturnableOrder(
    status="delivered", order_date=date(2026, 2, 3), estimated_delivery=date(2026, 2, 17)
)


def test_return_right_of_withdrawal_within_window():
    result = return_check(
        ORDER_DELIVERED, "arrependimento", today=date(2026, 2, 20), received_on=date(2026, 2, 17)
    )
    assert result["eligible"] is True
    assert result["escalate"] is False


def test_return_right_of_withdrawal_expired():
    result = return_check(ORDER_DELIVERED, "arrependimento", today=date(2026, 3, 23))
    assert result["eligible"] is False
    assert result["received_date_is_estimate"] is True


def test_return_defect_within_30_days_of_purchase():
    result = return_check(ORDER_DELIVERED, "defeito", today=date(2026, 2, 20))
    assert result["eligible"] is True
    assert result["path"] == "manufacturing_defect_exchange"


def test_return_defect_gray_zone_30_to_90_days_escalates():
    result = return_check(ORDER_DELIVERED, "defeito", today=date(2026, 3, 23))
    assert result["eligible"] is None
    assert result["escalate"] is True
    assert result["path"] == "warranty_gray_zone"


def test_return_defect_past_90_days_goes_to_manufacturer():
    result = return_check(ORDER_DELIVERED, "defeito", today=date(2026, 6, 1))
    assert result["eligible"] is False
    assert result["escalate"] is False
    assert result["path"] == "manufacturer_warranty"


def test_return_not_yet_delivered_escalates():
    pending = ReturnableOrder(status="confirmed", order_date=date(2026, 3, 10), estimated_delivery=None)
    result = return_check(pending, "arrependimento", today=date(2026, 3, 23))
    assert result["escalate"] is True
    assert result["path"] == "not_delivered_yet"


def test_return_shipped_not_received_yet():
    shipped = ReturnableOrder(status="shipped", order_date=date(2026, 2, 15), estimated_delivery=date(2026, 2, 28))
    result = return_check(shipped, "arrependimento", today=date(2026, 3, 23))
    assert result["eligible"] is False
    assert result["path"] == "in_transit"


def test_return_cancelled_order_is_not_applicable():
    cancelled = ReturnableOrder(status="cancelled", order_date=date(2026, 3, 8), estimated_delivery=None)
    result = return_check(cancelled, "arrependimento", today=date(2026, 3, 23))
    assert result["path"] == "cancelled"
