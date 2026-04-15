"""
BOT: PAIR CLIENT-FACING HANDLERS
Split from pairs.py to comply with line limits.
Simplified UI for paying customers.
"""
import logging
from aiogram import Router, F, types

from app.bot.handlers.utils import (
    repost_service, render_client_dashboard, render_client_stats_menu
)

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "c_support")
async def cb_client_support(callback: types.CallbackQuery):
    """Shows support options for clients."""
    from app.bot.keyboards import client_support_kb
    await callback.message.edit_text(
        "<b>💬 Customer Support</b>\n\n"
        "Need to add a source? Found a bug? Just message me directly.",
        reply_markup=client_support_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("c_tog_"))
async def cb_client_toggle_pair(callback: types.CallbackQuery):
    """Simple toggle for clients."""
    pair_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    try:
        pairs = await repost_service.get_user_pairs(user_id)
        target = next((p for p in pairs if p.id == pair_id), None)
        
        if target:
            if target.is_active:
                await repost_service.deactivate_pair(user_id, pair_id)
                await callback.answer("⏸ Channel Paused.")
            else:
                await repost_service.activate_pair(user_id, pair_id)
                await callback.answer("▶️ Channel Resumed.")
        
        await render_client_stats_menu(callback.message, user_id)
    except Exception as e:
        logger.error(f"Client toggle failed: {e}")
        await callback.answer("⚠️ Connection error.", show_alert=True)


@router.callback_query(F.data == "c_pauseall")
async def cb_client_pause_all(callback: types.CallbackQuery):
    """Pause everything for the client."""
    user_id = callback.from_user.id
    try:
        await repost_service.deactivate_all_pairs(user_id)
        await callback.answer("🛑 All channels paused.")
        await render_client_dashboard(callback.message, user_id)
    except Exception as e:
        logger.error(f"Client pause all failed: {e}")
        await callback.answer("⚠️ Action failed.", show_alert=True)
