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
    pairs = []
    is_admin = user_id in ADMIN_IDS if user_id else False

    if user_id:
        has_session = await repost_service.user_has_session(user_id)
        pairs = await repost_service.get_user_pairs(user_id)
        pair_count = len(pairs)
        active_count = sum(1 for p in pairs if p.is_active)
        error_count = sum(1 for p in pairs if getattr(p, "status", "") == "error")

    lines = [
        "Mister Reposter V2\n",
        f"Pairs: {pair_count}/{MAX_PAIRS}",
    ]
    if pair_count > 0:
        if error_count > 0:
            lines.append(f"Reposting: {'ON' if active_count > 0 else 'OFF'} ({error_count} with errors)")
        else:
            lines.append(f"Reposting: {'ON' if active_count > 0 else 'OFF'}")
    if has_session:
        lines.append("Session: Linked")
    else:
        lines.append("Session: Not linked")
    lines.append("\nUse the buttons below to navigate.")

    text = "\n".join(lines)
    if edit:
        await target.edit_text(text, reply_markup=main_menu_kb(has_session, is_admin))
    else:
        await target.answer(text, reply_markup=main_menu_kb(has_session, is_admin))


async def render_pairs_view(message: types.Message, user_id: int):
    pairs = await repost_service.get_user_pairs(user_id)

    if not pairs:
        await message.edit_text(
            "No pairs yet.\n"
            "\n"
            "Create your first repost pair to get started.",
            reply_markup=empty_pairs_kb()
        )
        return

    lines = [f"Your Repost Pairs  ({len(pairs)}/{MAX_PAIRS})\n"]

    STATUS_DISPLAY = {"active": "Active", "paused": "Paused", "error": "Error"}

    for p in pairs:
        pair_status = getattr(p, "status", None)
        if pair_status:
            status = STATUS_DISPLAY.get(pair_status, pair_status.title())
        else:
            status = "Active" if p.is_active else "Paused"
        schedule = SCHEDULE_LABELS.get(p.schedule_interval, "Instant") if p.schedule_interval else "Instant"
        filt = FILTER_LABELS.get(p.filter_type, "Unknown")
        extra = ""
        if hasattr(p, "start_from_msg_id") and p.start_from_msg_id:
            extra += f"  Start From: msg #{p.start_from_msg_id}\n"
        error_count = getattr(p, "error_count", 0) or 0
        if error_count > 0:
            extra += f"  Errors: {error_count}\n"

        lines.append(
            f"#{p.id}  [{status}]\n"
            f"  {p.source_id}  ->  {p.destination_id}\n"
            f"  Filter: {filt}  |  Schedule: {schedule}\n"
            f"{extra}"
        )

    await message.edit_text("\n".join(lines), reply_markup=pairs_kb(pairs))
