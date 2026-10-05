from django.db import models
from decimal import Decimal


class BotSettings(models.Model):
    class DeliveryMode(models.TextChoices):
        AUTO = "AUTO", "Avtomatik (Midasbuy/Mock)"
        MANUAL = "MANUAL", "Qo'lda (Admin)"

    class PaymentMethod(models.TextChoices):
        TEZCHECK = "TEZCHECK", "TezCheck"
        MANUAL_CARD = "MANUAL_CARD", "Karta orqali qo'lda"
        BALANCE = "BALANCE", "Ichki balans"

    bot_active = models.BooleanField(default=True, verbose_name="Bot faol")
    maintenance_mode = models.BooleanField(default=False, verbose_name="Texnik ta'mirlash rejimi")
    min_order_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("1000.00"), verbose_name="Minimal buyurtma summasi (UZS)"
    )
    max_order_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("15000000.00"), verbose_name="Maksimal buyurtma summasi (UZS)"
    )
    default_delivery_mode = models.CharField(
        max_length=16, choices=DeliveryMode.choices, default=DeliveryMode.MANUAL, verbose_name="Standart yetkazish rejimi"
    )
    default_payment_method = models.CharField(
        max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.TEZCHECK, verbose_name="Standart to'lov usuli"
    )
    card_number = models.CharField(
        max_length=32, default="8600 0000 0000 1234", verbose_name="To'lov karta raqami"
    )
    card_owner = models.CharField(
        max_length=128, default="PUBG UC ADMIN", verbose_name="Karta egasi ismi"
    )
    bank_name = models.CharField(
        max_length=64, default="Kapitalbank / Uzcard / Humo", verbose_name="Bank nomi"
    )
    support_username = models.CharField(
        max_length=64, default="@PubgUcSupport", verbose_name="Yordam (Support) username"
    )
    channel_username = models.CharField(
        max_length=64, default="@PubgUcNews", verbose_name="Rasmiy kanal"
    )
    referral_bonus = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("2000.00"), verbose_name="Referral bonusi (UZS)"
    )
    referral_reward_on_first_order = models.BooleanField(
        default=True, verbose_name="Bonus birinchi buyurtmada berilsinmi?"
    )
    currency = models.CharField(max_length=8, default="UZS", verbose_name="Valyuta")
    help_text = models.TextField(
        default="Assalomu alaykum! PUBG UC botimiz orqali tezkor va xavfsiz UC xarid qilishingiz mumkin.\nSavollaringiz bo'lsa adminga murojaat qiling.",
        verbose_name="Yordam matni"
    )
    about_text = models.TextField(
        default="🔥 PUBG Mobile UC Servis Bot\nRasmiy va arzon narxlardagi UC yetkazib berish xizmati!",
        verbose_name="Biz haqimizda matni"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Oxirgi o'zgartirilgan")

    class Meta:
        verbose_name = "Bot Sozlamasi"
        verbose_name_plural = "Bot Sozlamalari"

    def __str__(self):
        return f"Asosiy Sozlamalar ({'Faol' if self.bot_active else 'Nofaol'})"

    def save(self, *args, **kwargs):
        # Guarantee singleton row: id=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "BotSettings":
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
