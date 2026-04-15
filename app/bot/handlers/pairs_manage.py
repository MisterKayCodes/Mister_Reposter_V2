"""
BOT: PAIR MANAGEMENT HANDLERS
Split from pairs.py to comply with line limits.
Handles toggling, looping, and deleting pairs.
"""
import logging
from aiogram import Router, F, types

from app.bot.keyboards import delete_confirm_kb
from app.bot.handlers.utils import (
    render_pairs_view, repost_service, safe_callback_answer
)

logger = logging.getLogger(__name__)
router = Router()

# --- TOGGLE & LIST HANDLERS ---

@router.callback_query(F.data.startswith("tog_"))
async def cb_toggle_pair(callback: types.CallbackQuery):
    await safe_callback_answer(callback, "🔄 Processing...") 
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    try:
        pairs = await repost_service.get_user_pairs(user_id)
        target = next((p for p in pairs if p.id == pair_id), None)

        if not target:
            return await safe_callback_answer(callback, "❌ Pair not found.", show_alert=True)

        if target.is_active:
            await repost_service.deactivate_pair(user_id, pair_id)
        else:
            await repost_service.activate_pair(user_id, pair_id)
        
        await render_pairs_view(callback.message, user_id)
    except Exception as e:
        logger.error(f"Toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Connection lag.", show_alert=True)


@router.callback_query(F.data.startswith("loop_"))
async def cb_toggle_loop(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    try:
        new_state = await repost_service.toggle_pair_recycling(user_id, pair_id)
        status = "ENABLED" if new_state else "DISABLED"
        await safe_callback_answer(callback, f"♻️ Smart Loop: {status}")
        await render_pairs_view(callback.message, user_id)
    except Exception as e:
        logger.error(f"Loop toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Error updating setting.", show_alert=True)


# --- DELETE LOGIC ---

@router.callback_query(F.data.startswith("del_"))
async def cb_ask_delete(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    pair_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        f"<b>⚠️ Delete this Pair?</b>\n\nThis cannot be undone.",
        reply_markup=delete_confirm_kb(pair_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cdel_"))
async def cb_execute_delete(callback: types.CallbackQuery):
    await safe_callback_answer(callback, "🧨 Deleting...")
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    try:
        if await repost_service.delete_single_pair(user_id, pair_id):
            await render_pairs_view(callback.message, user_id)
        else:
            await safe_callback_answer(callback, "❌ Not found.", show_alert=True)
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        await safe_callback_answer(callback, "⚠️ Error.", show_alert=True)
