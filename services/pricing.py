"""Pure sale-price calculations and package block decisions."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_UP


@dataclass(frozen=True)
class PriceQuote:
    cost_uzs: Decimal
    sale_price: Decimal
    blocked_reason: str


def calculate_price(supplier_price_usd, usd_rate, profit_percent, max_price=0) -> PriceQuote:
    cost = Decimal(str(supplier_price_usd)) * Decimal(str(usd_rate))
    if cost <= 0 or Decimal(str(usd_rate)) <= 0:
        return PriceQuote(cost, Decimal("0"), "SUPPLIER_UNAVAILABLE")
    calculated = cost * (Decimal("1") + Decimal(str(profit_percent)) / Decimal("100"))
    # Round up to nearest 100 UZS so margin cannot be rounded below target.
    sale = (calculated / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_UP) * Decimal("100")
    maximum = Decimal(str(max_price or 0))
    reason = "MAX_PRICE_EXCEEDED" if maximum > 0 and sale > maximum else ""
    return PriceQuote(cost, sale, reason)


def product_sellable(product: dict) -> bool:
    return bool(
        product.get("is_active", 1) == 1
        and not product.get("manual_block")
        and not product.get("auto_block_reason")
        and float(product.get("supplier_price_usd", 0) or 0) > 0
        and product.get("supplier_product_id")
        and product.get("supplier_variation_id")
        and float(product.get("max_price", 0) or 0) > 0
        and float(product.get("price", 0) or 0) > 0
    )
