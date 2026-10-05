"""Handlers package."""
from .start import router as start_router
from .shop import router as shop_router
from .payment import router as payment_router
from .orders import router as orders_router
from .profile import router as profile_router
from .admin import router as admin_router

__all__ = [
    "start_router",
    "shop_router",
    "payment_router",
    "orders_router",
    "profile_router",
    "admin_router",
]
