import json
import os
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

# File to store verified users
VERIFIED_FILE = "data/verified_alerts.json"

# Get password from .env
ALERT_PASSCODE = os.getenv("ALERT_PASSCODE", "5135")

class AlertState(StatesGroup):
    waiting_for_password = State()

def load_verified_users():
    """Load list of verified user IDs"""
    try:
        with open(VERIFIED_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_verified_users(users):
    """Save verified user IDs"""
    with open(VERIFIED_FILE, "w") as f:
        json.dump(list(users), f)

@router.message(Command("alertbot"))
async def cmd_alertbot(message: types.Message, state: FSMContext):
    print(f"🔥 DEBUG: /alertbot command received from user {message.from_user.id}")
    user_id = message.from_user.id
    
    # Check if already verified
    verified = load_verified_users()
    if user_id in verified:
        await message.answer("✅ You are already verified! You will receive inventory alerts every hour.")
        return
    
    # Ask for password
    await state.set_state(AlertState.waiting_for_password)
    await message.answer("🔐 Enter the master passcode to enable inventory alerts:")

@router.message(AlertState.waiting_for_password)
async def check_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if message.text.strip() == ALERT_PASSCODE:
        verified = load_verified_users()
        verified.add(user_id)
        save_verified_users(verified)
        await state.clear()
        await message.answer(
            "✅ **VERIFIED!**\n\n"
            "You will now receive inventory alerts every hour.\n\n"
            "The bot will notify you when any pair is running low on content.\n\n"
            "Use /alertbot anytime to check your status."
        )
    else:
        await state.clear()
        await message.answer("❌ Wrong passcode! Access denied. Use /alertbot to try again.")