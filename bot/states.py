"""
BOT: STATES
Defines the conversation steps for the user. 
This acts as the short-term memory for multi-step processes.
"""
from aiogram.fsm.state import State, StatesGroup

class SessionUpload(StatesGroup):
    """Steps for linking a Telegram account."""
    waiting_for_input = State()  # Expecting a Base64 string or a .session file

class CreatePair(StatesGroup):
    """Steps for setting up a new reposting link."""
    waiting_for_source = State()      # Expecting source username/link
    waiting_for_destination = State() # Expecting destination username/link
    waiting_for_filter = State()      # Waiting for the user to click a filter button
    waiting_for_replacement = State() # Only used if 'Replace' mode is chosen