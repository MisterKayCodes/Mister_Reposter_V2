"""
BOT: LOGS HANDLER
Displays recent application logs via the Logs button.
Admin-only access — non-admin users are denied.
Follows architecture rules: callback-only, keyboard from keyboards.py.
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from app.bot.keyboards import logs_kb, migration_status_kb
from app.utils.log_buffer import log_buffer
from app.core.config import ADMIN_IDS
import json
from pathlib import Path

router = Router()


def _format_migration_card() -> str:
    data_dir = Path("data")
    checkpoints = list(data_dir.glob("checkpoint_migration_*.json"))
    
    if not checkpoints:
        return (
            "📦 <b>Channel Migration Status</b>\n\n"
            "<i>No active migration checkpoint found.</i>\n\n"
            "Run the migration script on the VPS to start sorting into VIP/VVIP."
        )

    cp_file = sorted(checkpoints, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    try:
        with open(cp_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return f"📦 <b>Migration Status</b>\n\nError reading checkpoint: {e}"

    last_id = data.get("last_scanned_id", 0)
    vip = data.get("vip_count", 0)
    vvip = data.get("vvip_count", 0)
    skipped = data.get("skipped_count", 0)
    total_sorted = vip + vvip + skipped

    return (
        "📦 <b>CHANNEL MIGRATION DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Source Message Pointer:</b> #{last_id}\n"
        f"<b>Total Items Evaluated:</b> {total_sorted}\n\n"
        f"• 📁 <b>VIP (2–6m):</b> <code>{vip}</code> videos forwarded\n"
        f"• 👑 <b>VVIP (6m+):</b> <code>{vvip}</code> videos forwarded\n"
        f"• ⏩ <b>Teasers (&lt;2m):</b> <code>{skipped}</code> clips preserved\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Checkpoint: {cp_file.name}</i>"
    )


@router.callback_query(F.data == "logs")
async def cb_view_logs(callback: types.CallbackQuery):
    from app.services.singleton import repost_service
    if not await repost_service.is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return

    raw = log_buffer.get_logs(25)
    if len(raw) > 4000:
        raw = raw[-4000:]

    await callback.message.edit_text(
        f"Recent Logs\n\n{raw}",
        reply_markup=logs_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "migration_status")
async def cb_view_migration_status(callback: types.CallbackQuery):
    from app.services.singleton import repost_service
    if not await repost_service.is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return

    text = _format_migration_card()
    await callback.message.edit_text(text, reply_markup=migration_status_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(Command("migration"))
async def cmd_migration_status(message: types.Message):
    from app.services.singleton import repost_service
    if not await repost_service.is_admin(message.from_user.id):
        return

    text = _format_migration_card()
    await message.answer(text, reply_markup=migration_status_kb(), parse_mode="HTML")
