"""
BOT: HANDLER UTILITIES
Shared render helpers used across handler modules.
"""
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import time
import logging
from app.services.singleton import repost_service
from app.bot.keyboards import (
    MAX_PAIRS, SCHEDULE_LABELS, FILTER_LABELS,
    main_menu_kb, pairs_kb,
    stats_pairs_kb, stats_detail_kb, back_kb,
    client_main_menu_kb, client_channels_kb, client_stats_kb
)
from app.core.repost.resolver import resolve_channel_input
from app.core.config import ADMIN_IDS

logger = logging.getLogger(__name__)


# --- TECH UTILS ---

async def safe_callback_answer(callback: types.CallbackQuery, text: str = None, show_alert: bool = False):
    """Rule 12: Prevents 'Query is too old' crashes."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        logger.debug(f"Query too old: {e}")

async def handle_channel_input(message: types.Message, state: FSMContext, step_name: str):
    """Rule 5 & 16: Standardized resolution logic."""
    if message.text and message.text.startswith("/"):
        return await message.answer("Please provide a channel, not a command.")

    resolved = resolve_channel_input(
        message.text if not message.forward_from_chat else None, 
        forwarded_chat=message.forward_from_chat
    )

    if not resolved["identifier"]:
        await message.answer(
            "Could not parse that input.\n"
            "Try a link, @username, or forward a message from the channel."
        )
        return None

    await state.update_data({
        f"{step_name}_id": resolved["identifier"],
        f"{step_name}_kind": resolved["kind"],
        f"{step_name}_invite_hash": resolved.get("invite_hash"),
        f"{step_name}_display": resolved.get("display_name"),
    })
    return resolved


def translate_error(error_str: str) -> str:
    if not error_str: return "Unknown Error."
    error_str = str(error_str).lower()
    if any(k in error_str for k in ["admin", "restricted", "permission", "forbidden"]):
        return "I need to be an Admin in the channel to post media!"
    if any(k in error_str for k in ["peer", "unreachable", "find"]):
        return "I can't find that channel anymore. Did it change names?"
    if any(k in error_str for k in ["banned", "deactivated"]):
        return "Telegram has temporarily restricted this account."
    if "flood" in error_str:
        return "Too many requests. Telegram is making us wait."
    return "Unknown Telegram Error. Check server logs."

async def render_stats_menu(message: types.Message, user_id: int):
    try:
        pairs = await repost_service.get_user_pairs(user_id)
        if not pairs:
            return await message.edit_text("<b>No pairs yet.</b>", reply_markup=back_kb(), parse_mode="HTML")
        await message.edit_text("<b>📊 Statistics Dashboard</b>", reply_markup=stats_pairs_kb(pairs), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error rendering stats menu: {e}")

def generate_stats_lines(stats, local_idx):
    """Rule 20: Unified stats formatting for user and admin views."""
    label = SCHEDULE_LABELS.get(stats["schedule"], "Instant")
    now = datetime.now().strftime("%H:%M:%S")
    lines = [f"<b>📊 Stats for Pair #{local_idx}</b>", f"<i>(Updated: {now})</i>\n"]
    
    if stats.get("last_error"):
        lines.append(f"⚠️ <b>PAUSED:</b> {translate_error(stats['last_error'])}\n")
        
    lines.extend([
        f"📫 <b>Source:</b> <code>{stats['source']}</code>",
        f"📬 <b>Destination:</b> <code>{stats['destination']}</code>",
        f"🕒 <b>Schedule:</b> {label}", "──────────────────"
    ])

    if stats["schedule"] and stats["schedule"] > 0:
        _add_backfill_stats(lines, stats)
    else:
        lines.append("ℹ️ <i>Stats for scheduled pairs only.</i>")
    
    return lines

async def render_pair_stats(message: types.Message, user_id: int, pair_id: int):
    try:
        stats = await repost_service.get_effective_stats(user_id, pair_id)
        if not stats:
            return await message.edit_text("❌ Pair not found.", reply_markup=back_kb())

        pairs = await repost_service.get_user_pairs(user_id)
        local_idx = 1
        for i, p in enumerate(pairs, 1):
            if p.id == stats['id']:
                local_idx = i
                break

        lines = generate_stats_lines(stats, local_idx)
        await message.edit_text("\n".join(lines), reply_markup=stats_detail_kb(stats['id']), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"TG Error: {e}")
    except Exception as e:
        logger.error(f"Stats error: {e}")

def _add_backfill_stats(lines: list, stats: dict):
    total = stats["total"]
    if total > 0:
        lines.append(f"📦 <b>Progress:</b> {stats['current']} / {total}")
        lines.append(f"📥 <b>Remaining:</b> {stats['remaining']} posts")
        _add_next_post_info(lines, stats)
        loop = "ON" if stats.get("loop_history") else "OFF"
        lines.append(f"♻️ <b>Recycling:</b> {loop}")
    elif total == 0:
        lines.append("⚠️ <b>Source appears to be empty.</b>")
    elif total == -1:
        lines.append("❌ <b>Access Error</b>")
    else:
        lines.append("<i>🔄 Stats pending...</i>")


def _add_next_post_info(lines: list, stats: dict):
    lines.append(f"🏁 <b>Est. Finish:</b> {format_time_left(stats['time_left_min'])}")
    next_p = stats.get("next_post")
    if next_p:
        time_until = int(max(0, next_p["time"] - time.time()) / 60)
        lines.append(f"⏳ <b>Next Post In:</b> {format_time_left(time_until)}")
        lines.append(f"📄 <b>Preview:</b> <code>{next_p['preview']}</code>")

async def render_main_menu(target: types.Message, user_id: int = None, edit: bool = True):
    has_session = False
    pair_count = 0
    active_count = 0
    error_count = 0
    is_admin = False
    if user_id:
        is_admin = await repost_service.is_admin(user_id)

    if user_id:
        has_session = await repost_service.user_has_session(user_id)
        pairs = await repost_service.get_user_pairs(user_id)
        pair_count = len(pairs)
        active_count = sum(1 for p in pairs if p.is_active)
        error_count = sum(1 for p in pairs if getattr(p, "status", "") == "error")

    lines = [f"<b>Mister Reposter V2</b>\n", f"Pairs: {pair_count}/{MAX_PAIRS}"]
    if pair_count > 0:
        status = "ON" if active_count > 0 else "OFF"
        lines.append(f"Reposting: {status}" + (f" (⚠️ {error_count} errors)" if error_count > 0 else ""))
            
    lines.append(f"Session: {'✅ Linked' if has_session else '❌ Not linked'}")
    text = "\n".join(lines)
    try:
        if edit: await target.edit_text(text, reply_markup=main_menu_kb(has_session, is_admin), parse_mode="HTML")
        else: await target.answer(text, reply_markup=main_menu_kb(has_session, is_admin), parse_mode="HTML")
    except Exception as e:
        logger.debug(f"Menu render failed: {e}")

def format_time_left(minutes: int) -> str:
    if minutes <= 0: return "0m"
    if minutes < 60: return f"{minutes}m"
    hours = minutes // 60
    if hours < 24: return f"{hours}h {minutes % 60}m"
    return f"{hours // 24}d {hours % 24}h"

async def render_pairs_view(message: types.Message, user_id: int, is_remote: bool = False):
    try:
        pairs = await repost_service.get_user_pairs(user_id)
        if not pairs:
            back_mark = f"uview_{user_id}" if is_remote else "main"
            return await message.edit_text("<b>No pairs yet.</b>", reply_markup=InlineKeyboardBuilder().button(text="Back", callback_data=back_mark).as_markup(), parse_mode="HTML")

        lines = [f"<b>Your Repost Pairs ({len(pairs)}/{MAX_PAIRS})</b>\n"]
        if is_remote:
            lines[0] = f"<b>📋 Remote View: User {user_id} ({len(pairs)}/{MAX_PAIRS})</b>\n"

        for idx, p in enumerate(pairs, 1):
            status = "🟢 Active" if p.is_active else "🟡 Paused"
            if getattr(p, "status", "") == "error": status = "🔴 Error"
            
            lines.append(f"<b>Pair #{idx} [{status}]</b>")
            src_display = getattr(p, "source_display", p.source_id)
            dest_display = getattr(p, "destination_display", p.destination_id)
            lines.append(f"<code>{src_display}</code> ➔ <code>{dest_display}</code>")
            
            if status == "🔴 Error":
                lines.append(f"⚠️ <i>{translate_error(repost_service.last_errors.get(p.id))}</i>")
                
            loop = "ON" if getattr(p, "loop_history", False) else "OFF"
            lines.append(f"Filter: {FILTER_LABELS.get(p.filter_type)} | Sched: {SCHEDULE_LABELS.get(p.schedule_interval)}")
            lines.append(f"<i>Pointer: msg #{p.start_from_msg_id or 1} | ♻️ Loop: {loop}</i>\n")

        await message.edit_text("\n".join(lines), reply_markup=pairs_kb(pairs, target_id=user_id if is_remote else None), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Pairs view error: {e}")


# --- CLIENT-FACING RENDERERS (SIMPLE UI) ---

async def render_client_dashboard(target: types.Message, user_id: int, edit: bool = True):
    """
    The 'Mister Reposter' simple dashboard for clients.
    Shows channel status and stats at a glance.
    """
    try:
        pairs = await repost_service.get_user_pairs(user_id)
        if not pairs:
            text = "<b>🔄 Mister Reposter</b>\n\nWelcome! No channels connected yet. Contact support to get started."
            kb = client_main_menu_kb() # Or a support-focused KB
        else:
            active_count = sum(1 for p in pairs if p.is_active)
            error_count = sum(1 for p in pairs if getattr(p, "status", "") == "error")
            
            lines = ["<b>🔄 Mister Reposter</b>\n", "Welcome back! Here's your channel status:\n"]
            
            for p in pairs:
                status_icon = "✅" if p.is_active else "⏸"
                if getattr(p, "status", "") == "error": status_icon = "⚠️"
                
                # Use destination_id as the channel identifier for the client
                lines.append(f"{status_icon} <b>{p.destination_id}</b>")
                
            text = "\n".join(lines)
            kb = client_main_menu_kb()

        if edit: await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else: await target.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Client dashboard error: {e}")


async def render_client_stats_menu(message: types.Message, user_id: int):
    """Lists client's channels for stats selection."""
    try:
        pairs = await repost_service.get_user_pairs(user_id)
        if not pairs:
            return await message.edit_text("<b>No channels connected.</b>", reply_markup=back_kb(), parse_mode="HTML")
        
        await message.edit_text(
            "<b>📊 Your Channels</b>\n\nSelect a channel to view detailed progress:",
            reply_markup=client_channels_kb(pairs),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Client stats menu error: {e}")


async def render_client_pair_stats(message: types.Message, user_id: int, pair_id: int):
    """Simplified statistics view for clients."""
    try:
        stats = await repost_service.get_effective_stats(user_id, pair_id)
        if not stats:
            return await message.edit_text("❌ Channel not found.", reply_markup=back_kb())

        status = "Active ✅" if stats.get("is_active") else "Paused ⏸"
        if stats.get("last_error"): 
            status = "⚠️ Issue detected (In progress)"

        mode_label = "Real-time" if not stats['schedule'] else f"Digest every {stats['schedule']}m"
        lines = [
            f"<b>📊 Progress: {stats['destination']}</b>\n",
            f"✅ <b>Status:</b> {status}",
            f"📬 <b>Total Delivered:</b> {stats['total'] if stats['total'] > 0 else 'Calculating...'}",
            "──────────────────",
            f"🕒 <b>Mode:</b> {mode_label}",
            f"📡 <b>Sources Connected:</b> 1" # Simplification
        ]

        if stats.get("last_reposted_at"):
            # Mocking last post time for UX feel
            lines.append(f"\n<i>Last post delivered recently.</i>")

        await message.edit_text("\n".join(lines), reply_markup=client_stats_kb(pair_id), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Client pair stats error: {e}")
