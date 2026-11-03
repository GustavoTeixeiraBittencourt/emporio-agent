from emporio_agent.data import fold, name_matches


def test_catalog_size_and_categories(catalog):
    assert len(catalog.products) == 65
    populated = {p.category_id for p in catalog.products}
    assert populated == {"1", "2", "3", "4", "5", "9"}
    assert len(catalog.categories) == 9


def test_only_four_active_promotions(catalog):
    active = {p.product_id for p in catalog.products if p.active_discount_percent}
    assert active == {"90", "94", "121", "127"}


def test_takamine_gd20_has_no_active_promo(catalog):
    gd20 = catalog.get("95")
    assert gd20.name.startswith("Takamine GD20")
    assert gd20.active_discount_percent is None
    assert gd20.effective_price == 2199.0


def test_typo_tolerance_in_search(catalog):
    result = catalog.search(query="takamie gd20")
    assert any(p["product_id"] == "95" for p in result["available"])


def test_spaced_query_matches_concatenated_model_code(catalog):
    result = catalog.search(query="gd 20")
    assert [p["product_id"] for p in result["available"]] == ["95"]


def test_digit_tokens_are_decisive_gf3d_vs_gf1r(catalog):
    gf3d = catalog.search(query="gf-3d")
    assert gf3d["available"] == []
    assert [p["product_id"] for p in gf3d["unavailable_matches"]] == ["96"]

    gf1r = catalog.search(query="gf-1r")
    assert [p["product_id"] for p in gf1r["available"]] == ["88"]


def test_guitars_under_1000_brl(catalog):
    result = catalog.search(category="Violões", max_price=1000)
    ids = {p["product_id"] for p in result["available"]}
    assert len(ids) == 12
    assert "96" not in ids  # Giannini GF-3D: out of stock, must not appear as buyable


def test_electroacoustic_filter_matches_only_shelby(catalog):
    result = catalog.search(category="Violões", max_price=1000, electric=True)
    assert [p["product_id"] for p in result["available"]] == ["107"]


def test_product_96_active_status_but_out_of_stock(catalog):
    p = catalog.get("96")
    assert p.status == "active"
    assert p.stock_quantity == 0
    assert p.availability == "out_of_stock"
    assert not p.is_buyable


def test_product_130_coming_soon_never_buyable_despite_stock(catalog):
    p = catalog.get("130")
    assert p.status == "coming_soon"
    assert p.stock_quantity > 0
    assert p.availability == "coming_soon"
    assert not p.is_buyable


def test_discontinued_products_113_and_136(catalog):
    for pid in ("113", "136"):
        p = catalog.get(pid)
        assert p.status == "discontinued"
        assert p.availability == "discontinued"
        assert not p.is_buyable


def test_public_view_never_leaks_exact_stock(catalog):
    for p in catalog.products:
        public = p.to_public()
        assert "stock_quantity" not in public
        assert "stock" not in public


def test_order_verification_by_email(orderbook):
    order = orderbook.verify("7", "leticia.rocha@jmail.com")
    assert order is not None
    assert order.order_id == "7"


def test_order_verification_by_phone_last_9_digits(orderbook):
    customer = orderbook.customers[orderbook.orders["7"].customer_id]
    order = orderbook.verify("7", customer.phone)
    assert order is not None


def test_order_verification_wrong_contact_fails(orderbook):
    assert orderbook.verify("7", "nope@nowhere.com") is None


def test_order_verification_another_customers_contact_fails(orderbook):
    # customers 11 and 43 share an email; using it for an unrelated order must fail
    assert orderbook.verify("7", "bruno.martins@jmail.com") is None


def test_shared_email_customers_11_and_43(orderbook):
    c11, c43 = orderbook.customers["11"], orderbook.customers["43"]
    assert fold(c11.email) == fold(c43.email)
    assert c11.customer_id != c43.customer_id


def test_order_3_total_mismatch_flag(orderbook):
    summary = orderbook.order_summary(orderbook.orders["3"])
    assert "total_mismatch" in summary["flags"]


def test_order_20_total_mismatch_flag(orderbook):
    summary = orderbook.order_summary(orderbook.orders["20"])
    assert "total_mismatch" in summary["flags"]


def test_order_8_overdue_shipment_flag(orderbook):
    summary = orderbook.order_summary(orderbook.orders["8"])
    assert "overdue_shipment" in summary["flags"]


def test_order_summary_never_exposes_contact_info(orderbook):
    summary = orderbook.order_summary(orderbook.orders["7"])
    assert "email" not in summary
    assert "phone" not in summary
    assert summary["customer_first_name"] == "Letícia"


def test_name_matches_restricted_to_name_not_description(catalog):
    # a word that only appears in the description, never the name, must not match
    p = catalog.get("95")
    assert name_matches("fingerstyle", p.name) is False
