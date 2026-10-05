from django.db import models
from decimal import Decimal
from apps.users.models import TelegramUser


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        TEZCHECK = "TEZCHECK", "TezCheck"
        MANUAL_CARD = "MANUAL_CARD", "Karta orqali qo'lda"
        BALANCE = "BALANCE", "Ichki balans"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Kutilmoqda"
        PAID = "PAID", "To'langan"
        FAILED = "FAILED", "Muvaffaqiyatsiz"
        CANCELLED = "CANCELLED", "Bekor qilingan"
        REFUNDED = "REFUNDED", "Qaytarilgan"

    payment_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="To'lov ID")
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="payments", verbose_name="Foydalanuvchi")
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name="Buyurtma"
    )
    payment_method = models.CharField(max_length=32, choices=PaymentMethod.choices, verbose_name="To'lov usuli")
    status = models.CharField(
        max_length=32, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True, verbose_name="Holat"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Summa (UZS)")
    currency = models.CharField(max_length=8, default="UZS", verbose_name="Valyuta")
    provider_transaction_id = models.CharField(
        max_length=128, blank=True, default="", db_index=True, verbose_name="Provider Tranzaksiya IDsi"
    )
    payment_url = models.TextField(blank=True, default="", verbose_name="To'lov havolasi (URL)")
    idempotency_key = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True, verbose_name="Idempotency kaliti"
    )
    raw_response = models.TextField(blank=True, default="", verbose_name="Provider javobi (JSON)")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="To'langan vaqt")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.payment_id} | {self.payment_method} | {self.amount} UZS | {self.status}"


class ManualPayment(models.Model):
    class ManualStatus(models.TextChoices):
        PENDING = "PENDING", "🟡 Kutilmoqda (Admin tekshiruvi)"
        APPROVED = "APPROVED", "✅ Tasdiqlangan"
        REJECTED = "REJECTED", "❌ Rad etilgan"

    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name="manual_details", verbose_name="Asosiy to'lov"
    )
    card_number = models.CharField(max_length=32, verbose_name="Karta raqami")
    card_owner = models.CharField(max_length=128, verbose_name="Karta egasi")
    screenshot = models.ImageField(upload_to="checks/%Y/%m/%d/", null=True, blank=True, verbose_name="Chek skrinshoti")
    telegram_file_id = models.CharField(max_length=256, blank=True, default="", verbose_name="Telegram File ID")
    status = models.CharField(
        max_length=32, choices=ManualStatus.choices, default=ManualStatus.PENDING, db_index=True, verbose_name="Tekshiruv holati"
    )
    reviewed_by = models.CharField(max_length=128, blank=True, default="", verbose_name="Tekshirgan admin")
    rejection_reason = models.TextField(blank=True, default="", verbose_name="Rad etish sababi")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tekshirilgan vaqt")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuborilgan vaqt")

    class Meta:
        verbose_name = "Qo'lda To'lov (Chek)"
        verbose_name_plural = "Qo'lda To'lovlar (Cheklar)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Chek #{self.id} - {self.payment.payment_id} ({self.status})"
