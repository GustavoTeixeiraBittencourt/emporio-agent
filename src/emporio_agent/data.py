"""In-memory loading, cleaning, and querying of the store's CSV data.

Everything is loaded once into plain dataclasses using the standard `csv`
module -- the dataset is tiny (dozens of rows), so there is no reason to
reach for pandas or a database. See README "Technical decisions" for why.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

from . import config

# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    """Lowercase and strip accents, e.g. 'Violões' -> 'violoes'."""
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(fold(text))


def _adjacent_pairs(tokens: list[str]) -> set[str]:
    return {tokens[i] + tokens[i + 1] for i in range(len(tokens) - 1)}


def _token_matches(query_token: str, product_tokens: list[str], product_pairs: set[str]) -> bool:
    has_digit = any(c.isdigit() for c in query_token)
    if query_token in product_tokens or query_token in product_pairs:
        return True
    if has_digit:
        # Tokens with a digit are decisive: "GF-3D" must never fuzzy-match
        # "GF-1R" just because the strings look similar.
        return False
    for pt in product_tokens:
        if len(query_token) >= 3 and (query_token in pt or pt in query_token):
            return True
        if SequenceMatcher(None, query_token, pt).ratio() >= 0.82:
            return True
    return False


def name_matches(query: str, name: str) -> bool:
    """True if every token of `query` is found (fuzzily, for non-digit
    tokens) in `name`. Matching is restricted to the product name (brand +
    model), never the free-text description."""
    q_tokens = _tokens(query)
    if not q_tokens:
        return True
    p_tokens = _tokens(name)
    p_pairs = _adjacent_pairs(p_tokens)

    i = 0
    while i < len(q_tokens):
        if i + 1 < len(q_tokens):
            pair = q_tokens[i] + q_tokens[i + 1]
            if pair in p_tokens or pair in p_pairs:
                i += 2
                continue
        if _token_matches(q_tokens[i], p_tokens, p_pairs):
            i += 1
            continue
        return False
    return True


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

AVAILABLE = "available"
LOW_STOCK = "low_stock"
OUT_OF_STOCK = "out_of_stock"
COMING_SOON = "coming_soon"
DISCONTINUED = "discontinued"

BUYABLE_STATES = {AVAILABLE, LOW_STOCK}


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    price_brl: float
    category_id: str
    category_name: str
    description: str
    stock_quantity: int
    status: str
    specs: dict
    created_at: str
    active_discount_percent: int | None = None

    @property
    def availability(self) -> str:
        if self.status == "discontinued":
            return DISCONTINUED
        if self.status == "coming_soon":
            return COMING_SOON
        if self.stock_quantity <= 0:
            return OUT_OF_STOCK
        if self.stock_quantity <= 2:
            return LOW_STOCK
        return AVAILABLE

    @property
    def is_buyable(self) -> bool:
        return self.availability in BUYABLE_STATES

    @property
    def effective_price(self) -> float:
        if self.active_discount_percent:
            return round(self.price_brl * (1 - self.active_discount_percent / 100), 2)
        return self.price_brl

    def to_public(self) -> dict:
        """Customer-facing view. Never exposes the exact stock count."""
        out = {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category_name,
            "price_brl": self.effective_price,
            "availability": self.availability,
        }
        if self.active_discount_percent:
            out["original_price_brl"] = self.price_brl
            out["discount_percent"] = self.active_discount_percent
        if self.availability == LOW_STOCK:
            out["note"] = "poucas unidades em estoque"
        return out


def _load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Catalog:
    def __init__(self, data_dir: Path | None = None):
        data_dir = Path(data_dir or config.DATA_DIR)
        categories_rows = _load_csv(data_dir / "desafio_tecnico_ai_eng - categories.csv")
        products_rows = _load_csv(data_dir / "desafio_tecnico_ai_eng - products.csv")
        promotions_rows = _load_csv(data_dir / "desafio_tecnico_ai_eng - promotions.csv")

        self.categories: dict[str, str] = {r["category_id"]: r["name"] for r in categories_rows}

        best_discount: dict[str, int] = {}
        for row in promotions_rows:
            if row["is_active"] == "1":
                pid = row["product_id"]
                pct = int(row["discount_percent"])
                if pct > best_discount.get(pid, 0):
                    best_discount[pid] = pct

        self.products: list[Product] = []
        for row in products_rows:
            pid = row["product_id"]
            self.products.append(
                Product(
                    product_id=pid,
                    name=row["name"],
                    price_brl=float(row["price_brl"]),
                    category_id=row["category_id"],
                    category_name=self.categories.get(row["category_id"], "Outros"),
                    description=row["description"],
                    stock_quantity=int(row["stock_quantity"]),
                    status=row["status"],
                    specs=json.loads(row["specs"]) if row["specs"] else {},
                    created_at=row["created_at"],
                    active_discount_percent=best_discount.get(pid),
                )
            )
        self._by_id = {p.product_id: p for p in self.products}

    def get(self, product_id: str) -> Product | None:
        return self._by_id.get(str(product_id))

    def list_category_names(self) -> list[str]:
        return list(self.categories.values())

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        strings: str | None = None,
        electric: bool | None = None,
    ) -> dict:
        """Structured + fuzzy-text search over the catalog.

        Returns {"available": [...], "unavailable_matches": [...]} -- both
        lists hold public dicts of products that match every filter; the
        first list is actually buyable, the second holds matches that are
        out of stock / coming soon / discontinued, so the agent can explain
        *why* something isn't orderable instead of pretending it doesn't
        exist.
        """
        category_id = None
        if category:
            cat_fold = fold(category)
            for cid, name in self.categories.items():
                if fold(name) == cat_fold or cid == str(category):
                    category_id = cid
                    break

        available: list[dict] = []
        unavailable: list[dict] = []

        for p in self.products:
            if category_id is not None and p.category_id != category_id:
                continue
            if query and not name_matches(query, p.name):
                continue
            price = p.effective_price
            if max_price is not None and price > max_price:
                continue
            if min_price is not None and price < min_price:
                continue
            if strings is not None:
                spec_strings = p.specs.get("strings")
                if spec_strings is None or fold(str(spec_strings)) != fold(str(strings)):
                    continue
            if electric is not None and "electronics" in p.specs:
                has_electronics = fold(str(p.specs["electronics"])) == "yes"
                if has_electronics != electric:
                    continue

            if p.is_buyable:
                available.append(p.to_public())
            else:
                unavailable.append(p.to_public())

        return {"available": available, "unavailable_matches": unavailable}


# ---------------------------------------------------------------------------
# Customers & orders
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    phone: str
    email: str
    city: str


@dataclass(frozen=True)
class OrderItem:
    product_id: str
    quantity: int
    product_name: str
    unit_price: float


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    order_date: date
    status: str
    total_brl: float
    payment_method: str
    tracking_code: str
    estimated_delivery: date | None
    notes: str
    items: list[OrderItem] = field(default_factory=list)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


class OrderBook:
    def __init__(self, data_dir: Path | None = None, catalog: Catalog | None = None):
        data_dir = Path(data_dir or config.DATA_DIR)
        self.catalog = catalog or Catalog(data_dir)

        customers_rows = _load_csv(data_dir / "desafio_tecnico_ai_eng - customers.csv")
        orders_rows = _load_csv(data_dir / "desafio_tecnico_ai_eng - orders.csv")
        items_rows = _load_csv(data_dir / "desafio_tecnico_ai_eng - order_items.csv")

        self.customers: dict[str, Customer] = {
            r["customer_id"]: Customer(
                customer_id=r["customer_id"],
                name=r["name"],
                phone=r["phone"],
                email=r["email"],
                city=r["city"],
            )
            for r in customers_rows
        }

        items_by_order: dict[str, list[OrderItem]] = {}
        for row in items_rows:
            product = self.catalog.get(row["product_id"])
            items_by_order.setdefault(row["order_id"], []).append(
                OrderItem(
                    product_id=row["product_id"],
                    quantity=int(row["quantity"]),
                    product_name=product.name if product else f"produto {row['product_id']}",
                    unit_price=product.price_brl if product else 0.0,
                )
            )

        self.orders: dict[str, Order] = {}
        for row in orders_rows:
            oid = row["order_id"]
            self.orders[oid] = Order(
                order_id=oid,
                customer_id=row["customer_id"],
                order_date=_parse_date(row["order_date"]),
                status=row["status"],
                total_brl=float(row["total_brl"]),
                payment_method=row["payment_method"],
                tracking_code=row["tracking_code"],
                estimated_delivery=_parse_date(row["estimated_delivery"]),
                notes=row["notes"],
                items=items_by_order.get(oid, []),
            )

    @staticmethod
    def _phone_digits(phone: str) -> str:
        return re.sub(r"\D", "", phone or "")

    def verify(self, order_id: str, contact: str) -> Order | None:
        """Return the order only if `contact` (email or phone) belongs to
        its customer. Never verify by name -- the dataset has duplicate
        names and at least one email shared by two different customers."""
        order = self.orders.get(str(order_id).strip())
        if order is None:
            return None
        customer = self.customers.get(order.customer_id)
        if customer is None:
            return None

        contact = (contact or "").strip()
        if "@" in contact:
            if fold(contact) == fold(customer.email):
                return order
            return None

        digits = self._phone_digits(contact)
        if len(digits) >= 9 and digits[-9:] == self._phone_digits(customer.phone)[-9:]:
            return order
        return None

    def order_summary(self, order: Order) -> dict:
        """Customer-facing summary: first name only (no phone/email), items,
        total, payment, tracking, ETA, and data-quality `flags`."""
        customer = self.customers.get(order.customer_id)
        first_name = customer.name.split()[0] if customer else ""

        items = [
            {
                "product_name": it.product_name,
                "quantity": it.quantity,
                "unit_price_brl": it.unit_price,
            }
            for it in order.items
        ]
        computed_total = round(sum(it.quantity * it.unit_price for it in order.items), 2)

        flags = []
        if order.items and abs(computed_total - order.total_brl) > 0.01:
            flags.append("total_mismatch")
        if order.status == "shipped" and order.estimated_delivery:
            if order.estimated_delivery < config.now().date():
                flags.append("overdue_shipment")
        if order.status == "confirmed" and not order.tracking_code:
            flags.append("not_yet_shipped")

        return {
            "order_id": order.order_id,
            "customer_first_name": first_name,
            "status": order.status,
            "order_date": order.order_date.isoformat() if order.order_date else None,
            "items": items,
            "total_brl": order.total_brl,
            "payment_method": order.payment_method,
            "tracking_code": order.tracking_code or None,
            "estimated_delivery": order.estimated_delivery.isoformat()
            if order.estimated_delivery
            else None,
            "flags": flags,
        }
