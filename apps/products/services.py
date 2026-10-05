from typing import List, Optional
from decimal import Decimal
from .models import Product


class ProductService:
    @staticmethod
    def get_active_products():
        """Retrieve all currently active UC packages sorted by sort_order."""
        return Product.objects.filter(is_active=True).order_by("sort_order", "uc_amount")

    @staticmethod
    def get_product(product_id: int) -> Optional[Product]:
        return Product.objects.filter(id=product_id, is_active=True).first()

    @staticmethod
    def seed_default_products():
        """Seed initial products if database table is empty."""
        if Product.objects.exists():
            return

        defaults = [
            {"name": "60 UC", "uc_amount": 60, "price": Decimal("15000.00"), "cost_price": Decimal("12000.00"), "sort_order": 1},
            {"name": "325 UC", "uc_amount": 325, "price": Decimal("70000.00"), "cost_price": Decimal("58000.00"), "sort_order": 2},
            {"name": "660 UC", "uc_amount": 660, "price": Decimal("135000.00"), "cost_price": Decimal("115000.00"), "sort_order": 3},
            {"name": "1800 UC", "uc_amount": 1800, "price": Decimal("350000.00"), "cost_price": Decimal("300000.00"), "sort_order": 4},
            {"name": "3850 UC", "uc_amount": 3850, "price": Decimal("700000.00"), "cost_price": Decimal("600000.00"), "sort_order": 5},
            {"name": "8100 UC", "uc_amount": 8100, "price": Decimal("1400000.00"), "cost_price": Decimal("1200000.00"), "sort_order": 6},
        ]

        for item in defaults:
            Product.objects.create(
                name=item["name"],
                uc_amount=item["uc_amount"],
                price=item["price"],
                cost_price=item["cost_price"],
                sort_order=item["sort_order"],
                provider=Product.ProviderType.MOCK,
                delivery_method=Product.DeliveryMethod.AUTO,
                is_active=True,
            )
