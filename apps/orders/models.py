from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
import uuid
from apps.users.models import TelegramUser
from apps.products.models import Product
from apps.promo.models import PromoCode


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Kutilmoqda"
        WAITING_PAYMENT = "WAITING_PAYMENT", "To'lov kutilmoqda"
        PAID = "PAID", "To'langan"
        PROCESSING = "PROCESSING", "Jarayonda"
        DELIVERING = "DELIVERING", "Yetkazilmoqda"
        COMPLETED = "COMPLETED", "Muvaffaqiyatli yakunlangan"
        FAILED = "FAILED", "Muvaffaqiyatsiz"
        CANCELLED = "CANCELLED", "Bekor qilingan"
        REFUNDED = "REFUNDED", "Qaytarilgan"
        MANUAL_REVIEW = "MANUAL_REVIEW", "Admin ko'rigida (Manual Review)"

    class PaymentMethod(models.TextChoices):
        TEZCHECK = "TEZCHECK", "TezCheck"
        MANUAL_CARD = "MANUAL_CARD", "Karta orqali qo'lda"
        BALANCE = "BALANCE", "Ichki balans"

    class ProviderChoice(models.TextChoices):
        MIDASBUY = "MIDASBUY", "Midasbuy API"
        MOCK = "MOCK", "Mock Provider"
        MANUAL = "MANUAL", "Qo'lda yetkazib berish (Manual)"

    order_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Buyurtma raqami")
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="orders", verbose_name="Foydalanuvchi")
    player_id = models.CharField(max_length=32, db_index=True, verbose_name="PUBG Player ID")
    player_nickname = models.CharField(max_length=128, blank=True, default="", verbose_name="Player Nickname")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="orders", verbose_name="Mahsulot")
    
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Asl narx (UZS)")
    discount_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"), verbose_name="Chegirma (UZS)"
    )
    final_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Yakuniy narx (UZS)")
    promo_code = models.ForeignKey(
        PromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders", verbose_name="Promo kod"
    )

    payment_method = models.CharField(max_length=32, choices=PaymentMethod.choices, verbose_name="To'lov usuli")
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True, verbose_name="Buyurtma holati"
    )
    provider = models.CharField(
        max_length=32, choices=ProviderChoice.choices, default=ProviderChoice.MOCK, verbose_name="Yetkazib beruvchi"
    )
    provider_order_id = models.CharField(
        max_length=128, blank=True, default="", db_index=True, verbose_name="Provider Buyurtma ID"
    )
    
    retry_count = models.PositiveSmallIntegerField(default=0, verbose_name="Qayta urinishlar soni")
    error_message = models.TextField(blank=True, default="", verbose_name="Xatolik xabari")
    idempotency_key = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True, verbose_name="Idempotency kaliti"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Yakunlangan vaqt")

    class Meta:
        verbose_name = "Buyurtma"
        verbose_name_plural = "Buyurtmalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_id} | {self.product.name} | {self.final_amount} UZS | {self.status}"

    @classmethod
    def generate_order_id(cls) -> str:
        """Generates sequential PUBG-YYYYMMDD-000001 style order ID."""
        today_str = timezone.now().strftime("%Y%m%d")
        prefix = f"PUBG-{today_str}-"
        # Find the last order created today
        last_order = cls.objects.filter(order_id__startswith=prefix).order_by("-order_id").first()
        if last_order:
            try:
                last_seq = int(last_order.order_id.split("-")[-1])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        return f"{prefix}{new_seq:06d}"

    @property
    def is_paid(self) -> bool:
        return self.status in [
            self.Status.PAID,
            self.Status.PROCESSING,
            self.Status.DELIVERING,
            self.Status.COMPLETED,
        ]
