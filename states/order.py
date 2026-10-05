from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    WAITING_PLAYER_ID = State()
    WAITING_PRODUCT = State()
    WAITING_PAYMENT_METHOD = State()
    WAITING_SCREENSHOT = State()


class AdminProductStates(StatesGroup):
    WAITING_NAME = State()
    WAITING_UC_AMOUNT = State()
    WAITING_PRICE = State()
    WAITING_NEW_PRICE = State()


class AdminSettingsStates(StatesGroup):
    WAITING_CARD_NUMBER = State()
    WAITING_CARD_OWNER = State()
    WAITING_BANK_NAME = State()
    WAITING_SUPPORT_USERNAME = State()
    WAITING_PROOF_CHANNEL_URL = State()
