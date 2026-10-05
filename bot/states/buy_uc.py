from aiogram.fsm.state import State, StatesGroup


class BuyUCStates(StatesGroup):
    WAITING_PLAYER_ID = State()
    WAITING_PLAYER_CONFIRMATION = State()
    WAITING_PRODUCT = State()
    WAITING_PROMO_CODE = State()
    WAITING_PAYMENT_METHOD = State()
    WAITING_PAYMENT = State()
    WAITING_SCREENSHOT = State()


class BalanceTopupStates(StatesGroup):
    WAITING_AMOUNT = State()
    WAITING_PAYMENT_METHOD = State()
    WAITING_SCREENSHOT = State()


class AdminStates(StatesGroup):
    WAITING_USER_ID_OR_SEARCH = State()
    WAITING_BALANCE_AMOUNT = State()
    WAITING_REJECTION_REASON = State()
    WAITING_BROADCAST_MESSAGE = State()
    WAITING_CARD_NUMBER = State()
    WAITING_CARD_OWNER = State()
