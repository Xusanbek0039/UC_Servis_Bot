from django.db import models
from apps.users.models import TelegramUser


class NotificationLog(models.Model):
    class NotificationType(models.TextChoices):
        ORDER_STATUS = "ORDER_STATUS", "Buyurtma holati"
        PAYMENT_CONFIRMATION = "PAYMENT_CONFIRMATION", "To'lov tasdig'i"
        ADMIN_ALERT = "ADMIN_ALERT", "Admin ogohlantirishi"
        BROADCAST = "BROADCAST", "Ommaviy xabar"
        SYSTEM = "SYSTEM", "Tizim xabari"

    user = models.ForeignKey(
        TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications", verbose_name="Foydalanuvchi"
    )
    telegram_id = models.BigIntegerField(db_index=True, verbose_name="Telegram ID")
    notification_type = models.CharField(
        max_length=32, choices=NotificationType.choices, default=NotificationType.ORDER_STATUS, verbose_name="Turi"
    )
    text = models.TextField(verbose_name="Xabar matni")
    is_sent = models.BooleanField(default=False, verbose_name="Yuborildi")
    error_message = models.TextField(blank=True, default="", verbose_name="Xatolik")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuborilgan vaqt")

    class Meta:
        verbose_name = "Xabarnoma Logi"
        verbose_name_plural = "Xabarnomalar Logi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.telegram_id} | {self.notification_type} | {'✅' if self.is_sent else '❌'}"
