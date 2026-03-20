"""
BOT: HANDLER UTILITIES
Shared render helpers used across handler modules.
"""
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
from services.repost_engine import RepostService
import logging
from bot.keyboards import (
    MAX_PAIRS, SCHEDULE_LABELS, FILTER_LABELS,
    main_menu_kb, pairs_kb, empty_pairs_kb,
    stats_pairs_kb, stats_detail_kb, back_kb
)
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
repost_service = RepostService()


async def render_stats_menu(message: types.Message, user_id: int):
    """Lists all pairs to selection dashboard."""
    try:
        pairs = await repost_service.get_user_pairs(user_id)
        if not pairs:
            await message.edit_text(
                "<b>No pairs yet.</b>\nCreate a pair to see statistics.",
                reply_markup=back_kb(),
                parse_mode="HTML"
            )
            return

        await message.edit_text(
            "<b>📊 Statistics Dashboard</b>\nSelect a pair below to view detailed progress, time estimates, and recycling status.",
            reply_markup=stats_pairs_kb(pairs),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            logger.error(f"Telegram error in render_stats_menu: {e}")
    except Exception as e:
        logger.error(f"Error rendering stats menu: {e}")
        await message.answer("⚠️ Error loading stats menu.")


async def render_pair_stats(message: types.Message, user_id: int, pair_id: int):
    """Shows detailed stats for a specific pair using the Core Engine."""
    try:
        stats = await repost_service.get_effective_stats(user_id, pair_id)
        if not stats:
            await message.edit_text("❌ Pair not found.", reply_markup=back_kb())
            return

        schedule_label = SCHEDULE_LABELS.get(stats["schedule"], "Instant")
        
        # Add a timestamp to ensure the message content changes on every "Refresh" click
        now = datetime.now().strftime("%H:%M:%S")
        
        lines = [
            f"<b>📊 Stats for Pair #{stats['id']}</b>",
            f"<i>(Last updated: {now})</i>\n",
            f"📫 <b>Source:</b> <code>{stats['source']}</code>",
            f"📬 <b>Destination:</b> <code>{stats['destination']}</code>",
            f"🕒 <b>Schedule:</b> {schedule_label}",
            "──────────────────"
        ]

        if stats["schedule"] and stats["schedule"] > 0:
            total = stats["total"]
            if total > 0:
                time_str = format_time_left(stats["time_left_min"])
                
                lines.append(f"📦 <b>Progress:</b> {stats['current']} / {total}")
                lines.append(f"📥 <b>Remaining:</b> {stats['remaining']} posts")
                lines.append(f"⏳ <b>Est. Finish:</b> {time_str}")
                lines.append(f"♻️ <b>Recycling:</b> ON")
            elif total == 0:
                lines.append("⚠️ <b>Source appears to be empty.</b>")
                lines.append("<i>Move some posts into the source channel to begin.</i>")
            elif total == -1:
                lines.append("❌ <b>Access Error</b>")
                lines.append("<i>Mister, I cannot read this source. Make sure you've joined it or it's public.</i>")
            else:
                lines.append("<i>🔄 Stats pending. Click Refresh or wait for next post.</i>")
        else:
            lines.append("ℹ️ <i>Stats are only calculated for scheduled (non-instant) pairs.</i>")

        await message.edit_text("\n".join(lines), reply_markup=stats_detail_kb(stats['id']), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass # Ignore redundant updates
        else:
            logger.error(f"Telegram error in render_pair_stats: {e}")
    except Exception as e:
        logger.error(f"Error rendering pair stats for {pair_id}: {e}")
        await message.answer("⚠️ Error loading detailed stats.")


async def render_main_menu(target: types.Message, user_id: int = None, edit: bool = True):
    has_session = False
    pair_count = 0
    active_count = 0
    error_count = 0
    is_admin = user_id in ADMIN_IDS if user_id else False

    if user_id:
        has_session = await repost_service.user_has_session(user_id)
        pairs = await repost_service.get_user_pairs(user_id)
        pair_count = len(pairs)
        active_count = sum(1 for p in pairs if p.is_active)
        # Rule 12: Explicit check for error status
        error_count = sum(1 for p in pairs if getattr(p, "status", "") == "error")

    lines = [
        "<b>Mister Reposter V2</b>\n",
        f"Pairs: {pair_count}/{MAX_PAIRS}",
    ]
    
    if pair_count > 0:
        status_text = "ON" if active_count > 0 else "OFF"
        if error_count > 0:
            lines.append(f"Reposting: {status_text} (⚠️ {error_count} errors)")
        else:
            lines.append(f"Reposting: {status_text}")
            
    lines.append(f"Session: {'✅ Linked' if has_session else '❌ Not linked'}")
    lines.append("\nUse the buttons below to navigate.")

    text = "\n".join(lines)
    # Rule 8: Use HTML for better visual hierarchy
    try:
        if edit:
            await target.edit_text(text, reply_markup=main_menu_kb(has_session, is_admin), parse_mode="HTML")
        else:
            await target.answer(text, reply_markup=main_menu_kb(has_session, is_admin), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            logger.error(f"Telegram error in render_main_menu: {e}")


def format_time_left(minutes: int) -> str:
    if minutes <= 0: return "0m"
    if minutes < 60: return f"{minutes}m"
    hours = minutes // 60
    if hours < 24: return f"{hours}h {minutes % 60}m"
    days = hours // 24
    return f"{days}d {hours % 24}h"


async def render_pairs_view(message: types.Message, user_id: int):
    try:
        pairs = await repost_service.get_user_pairs(user_id)

        if not pairs:
            await message.edit_text(
                "<b>No pairs yet.</b>\n\nCreate your first repost pair to get started.",
                reply_markup=empty_pairs_kb(),
                parse_mode="HTML"
            )
            return

        lines = [f"<b>Your Repost Pairs ({len(pairs)}/{MAX_PAIRS})</b>\n"]
        STATUS_DISPLAY = {"active": "🟢 Active", "paused": "🟡 Paused", "error": "🔴 Error"}

        for p in pairs:
            raw_status = getattr(p, "status", None)
            if not raw_status:
                status = "🟢 Active" if p.is_active else "🟡 Paused"
            else:
                status = STATUS_DISPLAY.get(raw_status, raw_status.title())

            schedule = SCHEDULE_LABELS.get(p.schedule_interval, "Instant")
            filt = FILTER_LABELS.get(p.filter_type, "Unknown")
            
            info = [
                f"<b>#{p.id} [{status}]</b>",
                f"<code>{p.source_id}</code> ➔ <code>{p.destination_id}</code>",
                f"Filter: {filt} | Schedule: {schedule}"
            ]

            # Simplified info for the Pairs list
            if p.start_from_msg_id:
                info.append(f"<i>Pointer: msg #{p.start_from_msg_id}</i>")
            
            errs = getattr(p, "error_count", 0) or 0
            if errs > 0:
                info.append(f"<i>Errors: {errs}/5</i>")

            lines.append("\n".join(info) + "\n")

        await message.edit_text("\n".join(lines), reply_markup=pairs_kb(pairs), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            logger.error(f"Telegram error in render_pairs_view: {e}")
    except Exception as e:
        logger.error(f"Error rendering pairs view: {e}")
        await message.answer("⚠️ Error loading pairs view.")