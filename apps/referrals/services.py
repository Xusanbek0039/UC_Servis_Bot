import logging
from decimal import Decimal
from django.db import transaction
from .models import ReferralRelationship, ReferralReward
from apps.users.models import TelegramUser, BalanceLedger
from apps.users.services import UserService
from apps.settings.models import BotSettings
from apps.notifications.services import NotificationService

logger = logging.getLogger("apps.referrals")


class ReferralService:
    @classmethod
    @transaction.atomic
    def process_referral_reward_for_order(cls, order) -> bool:
        """
        Grants referral bonus to referrer when referred user completes their first order.
        """
        user = order.user
        if not user.referrer:
            return False

        referrer = user.referrer

        # Check if reward was already given for this referred user
        already_rewarded = ReferralReward.objects.filter(
            referrer=referrer,
            referred_user=user,
            is_paid=True,
        ).exists()

        if already_rewarded:
            return False

        bot_settings = BotSettings.load()
        bonus_amount = bot_settings.referral_bonus

        if bonus_amount <= Decimal("0.00"):
            return False

        reward = ReferralReward.objects.create(
            referrer=referrer,
            referred_user=user,
            order_id=order.order_id,
            bonus_amount=bonus_amount,
            is_paid=True,
        )

        # Deposit bonus into referrer's account via atomic ledger
        UserService.update_balance(
            user=referrer,
            amount=bonus_amount,
            transaction_type=BalanceLedger.TransactionType.REFERRAL_BONUS,
            description=f"Do'stingiz ({user.display_name}) birinchi buyurtmasi uchun referral bonusi",
            reference_id=order.order_id,
        )

        logger.info(f"Referral bonus {bonus_amount} UZS given to {referrer.telegram_id} for user {user.telegram_id}")
        return True
