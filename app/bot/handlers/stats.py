"""
BOT: HANDLER - STATS
Handles the statistics dashboard and progress tracking.
"""
import logging
from aiogram import Router, F, types
from app.bot.handlers.utils import (
    render_stats_menu, render_pair_stats, repost_service,
    render_client_stats_menu, render_client_pair_stats
)
from app.core.config import ADMIN_IDS

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "stats")
async def handle_stats_menu(callback: types.CallbackQuery):
    """Shows the list of pairs for stats selection."""
    try:
        user_id = callback.from_user.id
        if await repost_service.is_admin(user_id):
            await render_stats_menu(callback.message, user_id)
        else:
            await render_client_stats_menu(callback.message, user_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_stats_menu: {e}")
        await callback.answer("⚠️ Could not load stats menu.", show_alert=True)

@router.callback_query(F.data.startswith("statp_"))
async def handle_pair_detail_stats(callback: types.CallbackQuery):
    """Shows detailed stats for a specific pair."""
    try:
        pair_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id
        
        if await repost_service.is_admin(user_id):
            await render_pair_stats(callback.message, user_id, pair_id)
        else:
            await render_client_pair_stats(callback.message, user_id, pair_id)
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


# --- CLIENT-FACING STATS HANDLERS ---

@router.callback_query(F.data == "c_stats")
async def handle_client_stats_menu(callback: types.CallbackQuery):
    """Client menu to pick which channel's stats to see."""
    try:
        await render_client_stats_menu(callback.message, callback.from_user.id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_client_stats_menu: {e}")
        await callback.answer("⚠️ Stats unavailable.", show_alert=True)


@router.callback_query(F.data.startswith("c_statp_"))
async def handle_client_pair_detail(callback: types.CallbackQuery):
    """Simplified progress for a specific client channel."""
    try:
        pair_id = int(callback.data.split("_")[2])
        await render_client_pair_stats(callback.message, callback.from_user.id, pair_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_client_pair_detail: {e}")
        await callback.answer("⚠️ Error loading stats.", show_alert=True)


@router.callback_query(F.data.startswith("c_refr_"))
async def handle_client_refresh(callback: types.CallbackQuery):
    """Simplified refresh for clients."""
    try:
        pair_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ Updating progress...")
        await repost_service.sync_pair_stats(callback.from_user.id, pair_id)
        await render_client_pair_stats(callback.message, callback.from_user.id, pair_id)
    except Exception as e:
        logger.error(f"Error in handle_client_refresh: {e}")
        await callback.answer("⚠️ Refresh failed.", show_alert=True)
