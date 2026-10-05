from django.db import models
from decimal import Decimal


class Product(models.Model):
    class ProviderType(models.TextChoices):
        MIDASBUY = "MIDASBUY", "Midasbuy API"
        MOCK = "MOCK", "Mock Provider"
        MANUAL = "MANUAL", "Qo'lda yetkazib berish (Manual)"

    class DeliveryMethod(models.TextChoices):
        AUTO = "AUTO", "Avtomatik"
        MANUAL = "MANUAL", "Qo'lda (Admin)"

    name = models.CharField(max_length=128, verbose_name="Paket nomi", help_text="Masalan: 60 UC")
    uc_amount = models.PositiveIntegerField(verbose_name="UC Miqdori")
    price = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Sotuv narxi (UZS)"
    )
    cost_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"), verbose_name="Tannarxi (UZS)"
    )
    provider = models.CharField(
        max_length=32, choices=ProviderType.choices, default=ProviderType.MOCK, verbose_name="Provider"
    )
    delivery_method = models.CharField(
        max_length=16, choices=DeliveryMethod.choices, default=DeliveryMethod.AUTO, verbose_name="Yetkazish usuli"
    )
    provider_product_id = models.CharField(
        max_length=64, blank=True, default="", verbose_name="Provider mahsulot IDsi", help_text="Midasbuy product code"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Faol")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")
    description = models.TextField(blank=True, default="", verbose_name="Tavsif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "UC Paketi"
        verbose_name_plural = "UC Paketlari"
        ordering = ["sort_order", "uc_amount"]

    def __str__(self):
        return f"{self.name} — {self.price:,.0f} so'm".replace(",", " ")

    @property
    def profit(self) -> Decimal:
        """Calculates expected profit per purchase."""
        return max(Decimal("0.00"), self.price - self.cost_price)
