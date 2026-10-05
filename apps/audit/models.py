from django.db import models


class AdminAction(models.Model):
    class ActionType(models.TextChoices):
        APPROVE_PAYMENT = "APPROVE_PAYMENT", "To'lovni tasdiqlash"
        REJECT_PAYMENT = "REJECT_PAYMENT", "To'lovni rad etish"
        COMPLETE_ORDER = "COMPLETE_ORDER", "Buyurtmani yakunlash (UC yuborildi)"
        CANCEL_ORDER = "CANCEL_ORDER", "Buyurtmani bekor qilish"
        RETRY_DELIVERY = "RETRY_DELIVERY", "Qayta yetkazish urinishi"
        UPDATE_BALANCE = "UPDATE_BALANCE", "Balansni o'zgartirish"
        UPDATE_SETTINGS = "UPDATE_SETTINGS", "Sozlamalarni o'zgartirish"
        OTHER = "OTHER", "Boshqa amal"

    admin_identifier = models.CharField(max_length=128, db_index=True, verbose_name="Admin (Telegram ID yoki Username)")
    action_type = models.CharField(max_length=32, choices=ActionType.choices, verbose_name="Amal turi")
    target_model = models.CharField(max_length=64, verbose_name="Nishon model")
    target_id = models.CharField(max_length=64, db_index=True, verbose_name="Nishon ID")
    details = models.TextField(blank=True, default="", verbose_name="Batafsil ma'lumot")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Bajarilgan vaqt")

    class Meta:
        verbose_name = "Admin Amali (Audit Log)"
        verbose_name_plural = "Admin Amallari (Audit Logs)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.admin_identifier} | {self.action_type} | {self.target_model}#{self.target_id} | {self.created_at:%Y-%m-%d %H:%M}"
