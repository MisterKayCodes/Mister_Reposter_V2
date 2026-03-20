"""
BOT: HANDLER - STATS
Handles the statistics dashboard and progress tracking.
"""
import logging
from aiogram import Router, F, types
from bot.handlers.utils import render_stats_menu, render_pair_stats, repost_service

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "stats")
async def handle_stats_menu(callback: types.CallbackQuery):
    """Shows the list of pairs for stats selection."""
    try:
        await render_stats_menu(callback.message, callback.from_user.id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_stats_menu: {e}")
        await callback.answer("⚠️ Could not load stats menu.", show_alert=True)

@router.callback_query(F.data.startswith("statp_"))
async def handle_pair_detail_stats(callback: types.CallbackQuery):
    """Shows detailed stats for a specific pair."""
    try:
        pair_id = int(callback.data.split("_")[1])
        await render_pair_stats(callback.message, callback.from_user.id, pair_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_pair_detail_stats: {e}")
        await callback.answer("⚠️ Could not load pair stats.", show_alert=True)

@router.callback_query(F.data.startswith("refr_"))
async def handle_refresh_stats(callback: types.CallbackQuery):
    """Force refreshes stats for a specific pair."""
    try:
        pair_id = int(callback.data.split("_")[1])
        await callback.answer("⏳ Refreshing statistics...")
        
        # Force sync
        await repost_service.sync_pair_stats(callback.from_user.id, pair_id)
        
        # Re-render
        await render_pair_stats(callback.message, callback.from_user.id, pair_id)
    except Exception as e:
        logger.error(f"Error in handle_refresh_stats: {e}")
        await callback.answer("⚠️ Failed to refresh stats.", show_alert=True)
