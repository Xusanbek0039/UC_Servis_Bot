from decimal import Decimal
from typing import Optional, Tuple
import logging
from django.db import transaction
from .models import TelegramUser, BalanceLedger, Player
from apps.settings.models import BotSettings
from apps.referrals.models import ReferralRelationship, ReferralReward

logger = logging.getLogger("apps.users")


class UserService:
    @staticmethod
    def get_or_create_user(
        telegram_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        referrer_telegram_id: Optional[int] = None,
    ) -> Tuple[TelegramUser, bool]:
        """
        Get or register user by Telegram ID.
        Handles referral link parsing and relationships.
        """
        user, created = TelegramUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "username": username,
                "first_name": first_name or "",
                "last_name": last_name or "",
            },
        )

        # Update profile if changed
        if not created:
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                user.save(update_fields=["username", "first_name", "last_name", "updated_at"])

        # Handle referral if newly created
        if created and referrer_telegram_id and referrer_telegram_id != telegram_id:
            try:
                referrer = TelegramUser.objects.filter(telegram_id=referrer_telegram_id).first()
                if referrer:
                    user.referrer = referrer
                    user.save(update_fields=["referrer"])
                    ReferralRelationship.objects.get_or_create(
                        referrer=referrer,
                        referred_user=user,
                    )
                    logger.info(f"User {telegram_id} linked to referrer {referrer_telegram_id}")
            except Exception as e:
                logger.error(f"Error linking referral for user {telegram_id}: {e}")

        return user, created

    @staticmethod
    def get_user(telegram_id: int) -> Optional[TelegramUser]:
        return TelegramUser.objects.filter(telegram_id=telegram_id).first()

    @staticmethod
    @transaction.atomic
    def update_balance(
        user: TelegramUser,
        amount: Decimal,
        transaction_type: str,
        description: str = "",
        reference_id: str = "",
    ) -> BalanceLedger:
        """
        Atomically modify user balance and record transaction in BalanceLedger.
        Never mutate balance directly outside this method.
        """
        # Lock user record for update to prevent race conditions
        locked_user = TelegramUser.objects.select_for_update().get(pk=user.pk)
        
        balance_before = locked_user.balance
        balance_after = balance_before + amount

        if balance_after < Decimal("0.00"):
            raise ValueError(
                f"Balansda mablag' yetarli emas! Mavjud: {balance_before:,.0f} UZS, so'ralgan: {abs(amount):,.0f} UZS"
            )

        locked_user.balance = balance_after
        locked_user.save(update_fields=["balance", "updated_at"])

        ledger_entry = BalanceLedger.objects.create(
            user=locked_user,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=description,
            reference_id=reference_id,
        )

        # Update in-memory user instance
        user.balance = balance_after
        logger.info(
            f"Balance updated for {user.telegram_id}: {balance_before} -> {balance_after} ({amount:+} UZS) [{transaction_type}]"
        )
        return ledger_entry

    @staticmethod
    def save_player(
        user: TelegramUser,
        player_id: str,
        nickname: str = "",
        region: str = "Global",
    ) -> Player:
        """Save or update player profile in user's saved players."""
        player, _ = Player.objects.update_or_create(
            user=user,
            player_id=player_id,
            defaults={
                "nickname": nickname,
                "region": region,
                "is_validated": True,
            },
        )
        return player
