"""
BOT: STATES
Defines the conversation steps for the user.
This acts as the short-term memory for multi-step processes.
"""
from aiogram.fsm.state import State, StatesGroup

class SessionUpload(StatesGroup):
    waiting_for_input = State()

class CreatePair(StatesGroup):
    waiting_for_source = State()
    waiting_for_destination = State()
    waiting_for_filter = State()
    waiting_for_replacement = State()
    waiting_for_schedule = State()
    waiting_for_start_message = State()
    waiting_for_confirmation = State()
