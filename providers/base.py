"""Base interfaces and custom exceptions for PUBG UC Top-Up Providers."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from decimal import Decimal
from pydantic import BaseModel, Field


# ==============================================================================
# Custom Exceptions
# ==============================================================================

class ProviderError(Exception):
    """Base exception for all external providers."""
    def __init__(self, message: str, provider: str = "Unknown", raw_data: Any = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.raw_data = raw_data


class PaymentError(ProviderError):
    """Raised when payment gateway encounters an issue."""
    pass


class InvalidWebhookError(PaymentError):
    """Raised when webhook signature verification fails or payload is malformed."""
    pass


class TopupError(ProviderError):
    """Base exception for UC top-up providers."""
    pass


class PlayerValidationError(TopupError):
    """Raised when PUBG player ID is invalid or cannot be verified."""
    pass


class DeliveryError(TopupError):
    """Raised when UC delivery to player account fails."""
    pass


# ==============================================================================
# Provider Data Schemas (Pydantic)
# ==============================================================================

class PlayerInfo(BaseModel):
    player_id: str
    nickname: str
    region: str = "Global"
    is_valid: bool = True
    level: Optional[int] = None
    avatar_url: Optional[str] = None


class ProviderProduct(BaseModel):
    product_id: str
    name: str
    uc_amount: int
    cost_price: Decimal
    currency: str = "UZS"


class TopupDeliveryResult(BaseModel):
    is_success: bool
    provider_order_id: str
    status: str  # COMPLETED, PROCESSING, FAILED
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class PaymentInitResult(BaseModel):
    is_success: bool
    payment_url: str
    provider_transaction_id: str
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class WebhookVerificationResult(BaseModel):
    is_valid: bool
    order_id: str
    provider_transaction_id: str
    amount: Decimal
    status: str  # PAID, FAILED, PENDING
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


# ==============================================================================
# Abstract Provider Interfaces
# ==============================================================================

class PaymentProvider(ABC):
    """Abstract interface for payment gateways (e.g., TezCheck)."""

    @abstractmethod
    async def create_payment(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: Optional[str] = None,
    ) -> PaymentInitResult:
        """Create payment session and get payment checkout URL."""
        pass

    @abstractmethod
    def verify_webhook(
        self,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> WebhookVerificationResult:
        """Verify webhook signature and parse payment status."""
        pass


class TopupProvider(ABC):
    """Abstract interface for PUBG Mobile UC top-up providers (Midasbuy, Mock, etc.)."""

    @abstractmethod
    async def validate_player(self, player_id: str) -> PlayerInfo:
        """Validate PUBG Player ID and return account nickname."""
        pass

    @abstractmethod
    async def get_products(self) -> List[ProviderProduct]:
        """Fetch available UC packages from provider."""
        pass

    @abstractmethod
    async def deliver(
        self,
        order_id: str,
        player_id: str,
        uc_amount: int,
        provider_product_id: Optional[str] = None,
    ) -> TopupDeliveryResult:
        """Deliver UC to the player's account."""
        pass

    @abstractmethod
    async def check_order(self, provider_order_id: str) -> TopupDeliveryResult:
        """Check status of a delivered/pending order."""
        pass
