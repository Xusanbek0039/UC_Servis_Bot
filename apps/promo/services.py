from decimal import Decimal
from typing import Tuple, Optional
from django.db import transaction
from .models import PromoCode, PromoCodeUsage
from apps.users.models import TelegramUser


class PromoService:
    @staticmethod
    def validate_promo(
        code: str,
        order_amount: Decimal,
        user: TelegramUser,
    ) -> Tuple[Optional[PromoCode], Decimal, str]:
        """
        Validate promo code and calculate discount amount.
        Returns: (promo_obj, discount_amount, error_or_success_message)
        """
        if not code:
            return None, Decimal("0.00"), ""

        cleaned_code = code.strip().upper()
        promo = PromoCode.objects.filter(code=cleaned_code, is_active=True).first()

        if not promo:
            return None, Decimal("0.00"), "Bunday promo kod mavjud emas yoki muddati o'tgan."

        # Check if user already used this promo code
        if PromoCodeUsage.objects.filter(promo=promo, user=user).exists():
            return None, Decimal("0.00"), "Siz ushbu promo koddan avval foydalangansiz."

        is_valid, msg = promo.is_valid(order_amount)
        if not is_valid:
            return None, Decimal("0.00"), msg

        discount = promo.calculate_discount(order_amount)
        return promo, discount, f"Promo kod muvaffaqiyatli qo'llandi! Chegirma: {discount:,.0f} UZS"

    @staticmethod
    @transaction.atomic
    def record_usage(
        promo: PromoCode,
        user: TelegramUser,
        order_id: str,
        discount_amount: Decimal,
    ) -> PromoCodeUsage:
        """Record promo code usage and increment its counter."""
        promo.used_count += 1
        promo.save(update_fields=["used_count"])

        return PromoCodeUsage.objects.create(
            promo=promo,
            user=user,
            order_id=order_id,
            discount_amount=discount_amount,
        )
