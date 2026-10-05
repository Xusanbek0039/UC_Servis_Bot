from django.db import models
from django.utils import timezone
from decimal import Decimal
from apps.users.models import TelegramUser


class PromoCode(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Foiz (%)"
        FIXED = "FIXED", "Aniq summa (UZS)"

    code = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="Promo kod")
    discount_type = models.CharField(
        max_length=16, choices=DiscountType.choices, default=DiscountType.PERCENTAGE, verbose_name="Chegirma turi"
    )
    discount_value = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Chegirma qiymati"
    )
    max_uses = models.PositiveIntegerField(default=100, verbose_name="Maksimal ishlatishlar soni")
    used_count = models.PositiveIntegerField(default=0, verbose_name="Ishlatilgan soni")
    min_order_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"), verbose_name="Minimal buyurtma summasi (UZS)"
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Amal qilish muddati")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Promo Kod"
        verbose_name_plural = "Promo Kodlar"
        ordering = ["-created_at"]

    def __str__(self):
        val = f"{self.discount_value}%" if self.discount_type == self.DiscountType.PERCENTAGE else f"{self.discount_value:,.0f} UZS"
        return f"{self.code} (-{val})"

    def is_valid(self, order_amount: Decimal) -> tuple[bool, str]:
        """Check whether the promo code can be applied to an order."""
        if not self.is_active:
            return False, "Promo kod faol emas."
        if self.expires_at and timezone.now() > self.expires_at:
            return False, "Promo kodning amal qilish muddati tugagan."
        if self.used_count >= self.max_uses:
            return False, "Ushbu promo koddan foydalanish limiti tugagan."
        if order_amount < self.min_order_amount:
            return False, f"Minimal buyurtma summasi {self.min_order_amount:,.0f} UZS bo'lishi kerak."
        return True, ""

    def calculate_discount(self, order_amount: Decimal) -> Decimal:
        """Calculate discount amount in UZS."""
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = (order_amount * self.discount_value) / Decimal("100.00")
        else:
            discount = self.discount_value
        return min(discount, order_amount)


class PromoCodeUsage(models.Model):
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="usages", verbose_name="Promo kod")
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="promo_usages", verbose_name="Foydalanuvchi")
    order_id = models.CharField(max_length=64, verbose_name="Buyurtma ID")
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Chegirma summasi (UZS)")
    used_at = models.DateTimeField(auto_now_add=True, verbose_name="Ishlatilgan vaqt")

    class Meta:
        verbose_name = "Promo Kod Ishlatilishi"
        verbose_name_plural = "Promo Kod Ishlatilishlari"
        unique_together = ("promo", "user", "order_id")
        ordering = ["-used_at"]

    def __str__(self):
        return f"{self.user.telegram_id} -> {self.promo.code} ({self.discount_amount} UZS)"
