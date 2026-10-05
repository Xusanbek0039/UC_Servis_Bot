"""Keyboards package."""
from .user import (
    main_menu_keyboard,
    products_keyboard,
    payment_methods_keyboard,
    tezcheck_pay_keyboard,
    cancel_keyboard,
)
from .admin import (
    admin_menu_keyboard,
    admin_orders_filter_keyboard,
    admin_order_detail_keyboard,
    admin_products_management_keyboard,
    admin_single_product_keyboard,
    admin_settings_keyboard,
)

__all__ = [
    "main_menu_keyboard",
    "products_keyboard",
    "payment_methods_keyboard",
    "tezcheck_pay_keyboard",
    "cancel_keyboard",
    "admin_menu_keyboard",
    "admin_orders_filter_keyboard",
    "admin_order_detail_keyboard",
    "admin_products_management_keyboard",
    "admin_single_product_keyboard",
    "admin_settings_keyboard",
]
