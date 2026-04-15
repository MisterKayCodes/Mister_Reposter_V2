"""
BOT: ADMIN SETTINGS HANDLERS
Allows admins to update global bot configurations (e.g., support username).
"""
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from app.bot.keyboards import back_kb
from app.bot.keyboards_admin import bot_settings_kb
from app.bot.states import BotSettings
from app.bot.handlers.utils import repost_service, safe_callback_answer
from app.data.database import async_session
from app.data.repository import UserRepository

logger = logging.getLogger(__name__)
router = Router()

async def _check_admin(user_id: int) -> bool:
    """Helper to verify admin status from DB."""
    async with async_session() as ds:
        user = await UserRepository(ds).get_user(user_id)
        return user.is_admin if user else False

@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "❌ Admin access required.", show_alert=True)
    
    async with async_session() as ds:
        repo = UserRepository(ds)
        owner = await repo.get_setting("owner_username", "Unknown")
        
        text = (
            "<b>⚙️ Bot Settings</b>\n\n"
            "Use this menu to manage global bot-wide variables.\n\n"
            f"<b>Current Support User:</b> @{owner.lstrip('@')}\n"
        )
        await callback.message.edit_text(
            text,
            reply_markup=bot_settings_kb(),
            parse_mode="HTML"
        )
    await safe_callback_answer(callback)

@router.callback_query(F.data == "edit_owner_user")
async def cb_edit_owner_user(callback: types.CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id): return
    
    await state.set_state(BotSettings.waiting_for_owner_username)
    await callback.message.edit_text(
        "📝 <b>Edit Support Username</b>\n\n"
        "Send the new Telegram username (e.g. <code>@MisterKayCodes</code>) that users should contact for support.",
        reply_markup=back_kb("admin_settings"),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)

@router.message(BotSettings.waiting_for_owner_username)
async def process_new_owner_user(message: types.Message, state: FSMContext):
    if not await _check_admin(message.from_user.id): return
    
    username = message.text.strip().lstrip("@")
    if not username or len(username) < 3:
        return await message.answer("❌ Invalid username. Please try again or cancel.")
    
    async with async_session() as ds:
        await UserRepository(ds).set_setting("owner_username", username)
    
    await state.clear()
    await message.answer(
        f"✅ <b>Settings Updated!</b>\n\nSupport username is now set to <code>@{username}</code>",
        reply_markup=back_kb("admin_settings"),
        parse_mode="HTML"
    )
