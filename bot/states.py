"""
BOT: STATES
Short-term Memory. (Anatomy: Mouth & Ears)
Defines the 'steps' a user is in during a conversation.
"""
from aiogram.fsm.state import State, StatesGroup

class SessionUpload(StatesGroup):
    waiting_for_input = State()  # The user is expected to send a string or file

class CreatePair(StatesGroup):
    waiting_for_source = State()
    waiting_for_destination = State()