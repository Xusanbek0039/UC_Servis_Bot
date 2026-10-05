from django.db import models
from decimal import Decimal


class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, db_index=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="Username")
    first_name = models.CharField(max_length=128, default="", blank=True, verbose_name="Ism")
    last_name = models.CharField(max_length=128, null=True, blank=True, verbose_name="Familiya")
    language_code = models.CharField(max_length=10, default="uz", verbose_name="Til")
    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"), verbose_name="Balans (UZS)"
    )
    is_admin = models.BooleanField(default=False, verbose_name="Admin statusi")
    is_banned = models.BooleanField(default=False, verbose_name="Bloklangan")
    referrer = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
        verbose_name="Taklif qilgan user",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ro'yxatdan o'tgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Telegram Foydalanuvchi"
        verbose_name_plural = "Telegram Foydalanuvchilar"
        ordering = ["-created_at"]

    def __str__(self):
        name = self.username or f"{self.first_name} {self.last_name or ''}".strip()
        return f"{name} ({self.telegram_id}) - {self.balance} UZS"

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return f"{self.first_name} {self.last_name or ''}".strip() or str(self.telegram_id)


class BalanceLedger(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Hisobni to'ldirish"
        WITHDRAW = "WITHDRAW", "Yechib olish"
        ORDER_PAYMENT = "ORDER_PAYMENT", "Buyurtma to'lovi"
        ORDER_REFUND = "ORDER_REFUND", "Buyurtma qaytarilishi (Refund)"
        REFERRAL_BONUS = "REFERRAL_BONUS", "Referral bonusi"
        ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT", "Admin tomonidan o'zgartirish"

    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="ledger_entries", verbose_name="Foydalanuvchi"
    )
    transaction_type = models.CharField(
        max_length=32, choices=TransactionType.choices, verbose_name="Operatsiya turi"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Summa (UZS)"
    )
    balance_before = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Oldingi balans (UZS)"
    )
    balance_after = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Keyingi balans (UZS)"
    )
    description = models.TextField(blank=True, default="", verbose_name="Izoh")
    reference_id = models.CharField(
        max_length=64, blank=True, default="", db_index=True, verbose_name="Bog'liq ID (Order/Payment)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Vaqt")

    class Meta:
        verbose_name = "Balans Tarixi (Ledger)"
        verbose_name_plural = "Balans Tarixi (Ledgers)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.telegram_id} | {self.transaction_type} | {self.amount} UZS | {self.created_at:%Y-%m-%d %H:%M}"


class Player(models.Model):
    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="saved_players", verbose_name="Foydalanuvchi"
    )
    player_id = models.CharField(max_length=32, db_index=True, verbose_name="PUBG Player ID")
    nickname = models.CharField(max_length=128, default="", blank=True, verbose_name="Player Nickname")
    region = models.CharField(max_length=64, default="Global", verbose_name="Region/Server")
    is_validated = models.BooleanField(default=True, verbose_name="Tasdiqlangan")
    last_used_at = models.DateTimeField(auto_now=True, verbose_name="Oxirgi ishlatilgan")

    class Meta:
        verbose_name = "PUBG Player"
        verbose_name_plural = "PUBG Playerlar"
        unique_together = ("user", "player_id")
        ordering = ["-last_used_at"]

    def __str__(self):
        return f"{self.nickname or 'Noma\'lum'} ({self.player_id})"
