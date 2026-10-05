from django.db import models
from decimal import Decimal
from apps.users.models import TelegramUser


class ReferralRelationship(models.Model):
    referrer = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="referral_invites", verbose_name="Taklif qiluvchi"
    )
    referred_user = models.OneToOneField(
        TelegramUser, on_delete=models.CASCADE, related_name="referred_by_relation", verbose_name="Taklif qilingan"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan sana")

    class Meta:
        verbose_name = "Referral Bog'lanishi"
        verbose_name_plural = "Referral Bog'lanishlari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer.display_name} -> {self.referred_user.display_name}"


class ReferralReward(models.Model):
    referrer = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="referral_rewards", verbose_name="Taklif qiluvchi"
    )
    referred_user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="generated_rewards", verbose_name="Taklif qilingan"
    )
    order_id = models.CharField(max_length=64, blank=True, default="", verbose_name="Buyurtma ID")
    bonus_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"), verbose_name="Mukofot summasi (UZS)"
    )
    is_paid = models.BooleanField(default=False, verbose_name="To'langan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Referral Mukofoti"
        verbose_name_plural = "Referral Mukofotlari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer.display_name} +{self.bonus_amount} UZS ({self.referred_user.display_name})"
