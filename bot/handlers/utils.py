"""
BOT: HANDLER UTILITIES
Shared render helpers used across handler modules.
"""
from aiogram import types
from services.repost_engine import RepostService
from bot.keyboards import (
    MAX_PAIRS, SCHEDULE_LABELS, FILTER_LABELS,
    main_menu_kb, pairs_kb, empty_pairs_kb,
)
from config import ADMIN_IDS

repost_service = RepostService()

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
    if edit:
        await target.edit_text(text, reply_markup=main_menu_kb(has_session, is_admin), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=main_menu_kb(has_session, is_admin), parse_mode="HTML")


async def render_pairs_view(message: types.Message, user_id: int):
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
        # Rule 4.1.6: Dynamic badge logic
        raw_status = getattr(p, "status", None)
        if not raw_status:
            status = "🟢 Active" if p.is_active else "🟡 Paused"
        else:
            status = STATUS_DISPLAY.get(raw_status, raw_status.title())

        schedule = SCHEDULE_LABELS.get(p.schedule_interval, "Instant")
        filt = FILTER_LABELS.get(p.filter_type, "Unknown")
        
        # Build the info block
        info = [
            f"<b>#{p.id} [{status}]</b>",
            f"<code>{p.source_id}</code> ➔ <code>{p.destination_id}</code>",
            f"Filter: {filt} | Schedule: {schedule}"
        ]

        # Rule 4.1.13: Show error counts and start message tracking
        if getattr(p, "start_from_msg_id", None):
            info.append(f"<i>Start From: msg #{p.start_from_msg_id}</i>")
        
        errs = getattr(p, "error_count", 0) or 0
        if errs > 0:
            info.append(f"<i>Errors: {errs}/5</i>")

        lines.append("\n".join(info) + "\n")

    await message.edit_text("\n".join(lines), reply_markup=pairs_kb(pairs), parse_mode="HTML")