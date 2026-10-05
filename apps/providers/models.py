from django.db import models


class ProviderTransaction(models.Model):
    class ProviderName(models.TextChoices):
        TEZCHECK = "TEZCHECK", "TezCheck"
        MIDASBUY = "MIDASBUY", "Midasbuy"
        MOCK = "MOCK", "Mock Provider"
        MANUAL = "MANUAL", "Manual"

    provider = models.CharField(max_length=32, choices=ProviderName.choices, db_index=True, verbose_name="Provider")
    action = models.CharField(max_length=64, db_index=True, verbose_name="Amal (Action)")
    reference_id = models.CharField(max_length=64, blank=True, default="", db_index=True, verbose_name="Bog'liq ID")
    request_payload = models.TextField(blank=True, default="", verbose_name="Yuborilgan ma'lumot")
    response_payload = models.TextField(blank=True, default="", verbose_name="Qabul qilingan ma'lumot")
    status_code = models.IntegerField(null=True, blank=True, verbose_name="HTTP Status kod")
    is_success = models.BooleanField(default=False, verbose_name="Muvaffaqiyatli")
    error_message = models.TextField(blank=True, default="", verbose_name="Xatolik xabari")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Provider Tranzaksiyasi"
        verbose_name_plural = "Provider Tranzaksiyalari"
        ordering = ["-created_at"]

    def __str__(self):
        status = "✅" if self.is_success else "❌"
        return f"{self.provider} | {self.action} | {status} | {self.created_at:%Y-%m-%d %H:%M:%S}"
